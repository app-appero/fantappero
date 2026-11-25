"""Sostituto dopo uno scambio sbilanciato (1.5, decisione del 25/11).

Uno scambio eseguito che lascia una squadra sotto la misura della rosa (2 per 1: 34/35) le dà
il diritto di comprare subito, anche a mercato chiuso, un calciatore libero del ruolo che manca,
al suo Valore. Il diritto nasce solo dallo scambio (registro ``trade_replacements``); le righe
aperte si chiudono da sole se la rosa torna alla misura in altro modo; la formazione torna
salvabile appena la rosa è di nuovo completa.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (
    _fill_full_roster,
    _lineup_payload,
    _register_and_login,
    _seed_clubs_and_round,
)

from auth.models.user import User
from database.enums import (
    CreditLedgerReason,
    FantasyRole,
    FantasyTurnStatus,
    LeagueMemberRole,
    LeagueState,
    MarketSessionKind,
    MarketSessionStatus,
    PlatformRole,
    RosterCompositionStatus,
    TradeReplacementStatus,
)
from database.session import create_session_factory
from fantasy_teams.composition_service import sync_team_composition_status
from fantasy_teams.models import CreditAccount, CreditLedgerEntry, FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from market.models import MarketBid, MarketSession, TradeReplacement
from market.valuation_service import load_market_info
from notifications.models import Notification
from sports_data.catalog.models import Club
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _league(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    prefix: str,
    id_offset: int,
    teams: int = 2,
) -> dict:
    """Lega avviata con ``teams`` squadre a rosa completa e convalidata e un turno aperto.

    La prima squadra è dell'amministratore (chi crea la lega).
    """
    users = [_register_and_login(client, f"{prefix}.{index}@example.com") for index in range(teams)]
    created = client.post(
        "/leagues",
        headers=_headers(users[0][0]),
        json={"name": f"Lega {prefix}", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    for _token, user_id in users[1:]:
        db_session.add(
            LeagueMembership(
                league_id=UUID(league_id), user_id=user_id, role=LeagueMemberRole.MEMBER
            )
        )
    db_session.commit()
    team_ids = [
        client.get(f"/leagues/{league_id}/rosa", headers=_headers(token)).json()["id"]
        for token, _user_id in users
    ]
    fantasy_round, clubs = _seed_clubs_and_round(
        db_session, league_id, competition_ids, id_offset=id_offset
    )
    roles = [
        _fill_full_roster(
            db_session,
            team_id,
            clubs,
            provider_offset=id_offset + 1_000 * (index + 1),
            label=f"{prefix[-6:]}{index}",
            record_ownership=True,
        )
        for index, team_id in enumerate(team_ids)
    ]
    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.state = LeagueState.ACTIVE
    db_session.flush()
    for team_id in team_ids:
        team = db_session.get(FantasyTeam, UUID(team_id))
        assert team is not None
        report = sync_team_composition_status(db_session, team, league=league)
        assert report.status == RosterCompositionStatus.VALIDATED, report.issues
    db_session.commit()
    role_of = {
        athlete_id: role for by_role in roles for role, ids in by_role.items() for athlete_id in ids
    }
    return {
        "league_id": league_id,
        "round_id": str(fantasy_round.id),
        "tokens": [token for token, _ in users],
        "user_ids": [user_id for _, user_id in users],
        "teams": team_ids,
        "roles": roles,
        "role_of": role_of,
        "clubs": clubs,
        "id_offset": id_offset,
    }


def _free_athletes(
    db_session: Session,
    setup: dict,
    *,
    role: FantasyRole,
    count: int,
    provider_offset: int,
    label: str,
) -> list[UUID]:
    """Calciatori nel listone della lega e in nessuna rosa: i «liberi»."""
    ids: list[UUID] = []
    clubs: list[Club] = setup["clubs"]
    for index in range(count):
        athlete = Athlete(provider_id=provider_offset + index, canonical_name=f"{label} {index}")
        db_session.add(athlete)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                athlete_id=athlete.id,
                season_year=2026,
                role=role,
                mapping_version="v1.0.0",
                provider_position_raw=role.value,
                club_id=clubs[index % len(clubs)].id,
            )
        )
        ids.append(athlete.id)
        setup["role_of"][athlete.id] = role
    db_session.commit()
    return ids


def _trade(
    client: TestClient,
    setup: dict,
    *,
    proposer: int,
    recipient: int,
    offered: list[UUID],
    requested: list[UUID],
    accept: bool = True,
) -> dict:
    league_id = setup["league_id"]
    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers=_headers(setup["tokens"][proposer]),
        json={
            "recipientTeamId": setup["teams"][recipient],
            "offeredAthleteIds": [str(item) for item in offered],
            "requestedAthleteIds": [str(item) for item in requested],
            "offeredCredits": 0,
            "requestedCredits": 0,
            "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        },
    )
    assert proposal.status_code == 201, proposal.json()
    if not accept:
        return proposal.json()
    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal.json()['id']}/accetta",
        headers=_headers(setup["tokens"][recipient]),
    )
    assert accepted.status_code == 200, accepted.json()
    return accepted.json()


def _status(client: TestClient, setup: dict, team: int) -> dict:
    response = client.get(
        f"/leagues/{setup['league_id']}/mercato/sostituti",
        headers=_headers(setup["tokens"][team]),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def _candidates(client: TestClient, setup: dict, team: int, **params: str) -> dict:
    response = client.get(
        f"/leagues/{setup['league_id']}/mercato/sostituti/liberi",
        headers=_headers(setup["tokens"][team]),
        params=params,
    )
    assert response.status_code == 200, response.json()
    return response.json()


def _buy(client: TestClient, setup: dict, team: int, athlete_id: UUID):
    return client.post(
        f"/leagues/{setup['league_id']}/mercato/sostituti/acquista",
        headers=_headers(setup["tokens"][team]),
        json={"athleteId": str(athlete_id)},
    )


def _rows(db_session: Session, team_id: str) -> list[TradeReplacement]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(TradeReplacement)
            .where(TradeReplacement.fantasy_team_id == UUID(team_id))
            .order_by(TradeReplacement.created_at.asc(), TradeReplacement.id.asc())
        ).all()
    )


def _occupied(db_session: Session, team_id: str) -> list[FantasyRosterSlot]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == UUID(team_id),
                FantasyRosterSlot.athlete_id.is_not(None),
            )
        ).all()
    )


def _balance(db_session: Session, team_id: str) -> int:
    db_session.expire_all()
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    return account.balance


def _save_lineup(client: TestClient, db_session: Session, setup: dict, team: int):
    slots = _occupied(db_session, setup["teams"][team])
    return client.put(
        f"/leagues/{setup['league_id']}/turni/{setup['round_id']}/formazione",
        headers=_headers(setup["tokens"][team]),
        json=_lineup_payload(slots, setup["role_of"]),
    )


def _close_market(db_session: Session, league_id: str) -> None:
    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.market_open = False
    db_session.commit()


def _price(db_session: Session, league_id: str, athlete_id: UUID) -> int:
    info = load_market_info(db_session, league_id=UUID(league_id), athlete_ids=[athlete_id])
    value = info[athlete_id].market_value
    assert value is not None and value >= 1
    return value


def test_two_for_one_trade_gives_one_replacement_bought_at_value_with_market_closed(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.duexuno", id_offset=8_100_000)
    team_a, team_b = setup["teams"]
    free_d = _free_athletes(
        db_session, setup, role=FantasyRole.D, count=3, provider_offset=8_190_000, label="Libero D"
    )
    free_c = _free_athletes(
        db_session, setup, role=FantasyRole.C, count=1, provider_offset=8_191_000, label="Libero C"
    )
    incoming = setup["roles"][1][FantasyRole.C][0]
    # A cede due difensori per un centrocampista: A resta a 34/35, B sale a 36/35.
    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][:2],
        requested=[incoming],
    )

    rows = _rows(db_session, team_a)
    assert [(row.role, row.status) for row in rows] == [
        (FantasyRole.D, TradeReplacementStatus.PENDING)
    ]
    assert _rows(db_session, team_b) == []  # chi sale a 36 segue la regola dell'esubero

    status = _status(client, setup, 0)
    assert status["filledSlots"] == 34
    assert status["rosterSize"] == 35
    assert status["missingRoles"] == [{"role": "D", "count": 1}]
    incoming_athlete = db_session.get(Athlete, incoming)
    assert incoming_athlete is not None
    assert status["receivedAthleteNames"] == [incoming_athlete.canonical_name]
    assert status["otherTeamName"]
    assert status["blockedReason"] is None
    assert _status(client, setup, 1)["pending"] == []

    # Notifica a chi era assente (il proponente), non a chi ha appena accettato.
    notices = db_session.scalars(
        select(Notification).where(
            Notification.template_key == "mercato.sostituto_scambio",
            Notification.user_id.in_(setup["user_ids"]),
        )
    ).all()
    assert [row.user_id for row in notices] == [setup["user_ids"][0]]
    assert notices[0].title == "Scegli il sostituto dopo lo scambio"
    assert "ti manca 1 Difensore" in notices[0].body
    assert notices[0].deep_link == f"/rosa?sostituto=1&lega={setup['league_id']}"

    # Senza sostituto la formazione resta bloccata, con il motivo.
    blocked = _save_lineup(client, db_session, setup, 0)
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "roster_not_validated"
    assert blocked.json()["message"].startswith("Rosa incompleta: 34 giocatori su 35.")
    assert "sostituto" in blocked.json()["message"]

    # Solo i liberi del ruolo che manca, con il Valore come prezzo.
    listing = _candidates(client, setup, 0, cerca="Libero")
    assert listing["role"] == "D"
    ids = {item["athleteId"] for item in listing["candidates"]}
    assert ids == {str(item) for item in free_d}
    assert str(free_c[0]) not in ids
    owned = {str(slot.athlete_id) for slot in _occupied(db_session, team_b)}
    assert not owned & {item["athleteId"] for item in _candidates(client, setup, 0)["candidates"]}
    values = [item["marketValue"] for item in listing["candidates"]]
    assert values == sorted(values, reverse=True)

    # A mercato chiuso il sostituto si compra lo stesso: è solo un completamento della rosa.
    _close_market(db_session, setup["league_id"])
    before = _balance(db_session, team_a)
    price = _price(db_session, setup["league_id"], free_d[0])
    bought = _buy(client, setup, 0, free_d[0])
    assert bought.status_code == 200, bought.json()
    body = bought.json()
    assert body["priceCredits"] == price
    assert body["balance"] == before - price
    assert body["status"]["pending"] == []
    assert body["status"]["filledSlots"] == 35
    assert _balance(db_session, team_a) == before - price

    rows = _rows(db_session, team_a)
    assert rows[0].status == TradeReplacementStatus.CHOSEN
    assert rows[0].athlete_id == free_d[0]
    assert rows[0].price_credits == price
    assert rows[0].chosen_at is not None

    entry = db_session.scalar(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.transaction_id == f"trade-replacement:{rows[0].id}"
        )
    )
    assert entry is not None
    assert entry.amount == -price
    assert entry.reason == CreditLedgerReason.ROSTER_PURCHASE
    assert entry.note == "Sostituto dopo lo scambio: Libero D 0"
    history = client.get(
        f"/leagues/{setup['league_id']}/mercato/storico",
        headers=_headers(setup["tokens"][1]),
        params={"category": "acquisto"},
    )
    assert history.status_code == 200
    assert "market_trade_replacement_purchased" in {
        item["action"] for item in history.json()["items"]
    }

    # La rosa torna 35/35 e la formazione si salva subito; lo stato salvato è aggiornato.
    saved = _save_lineup(client, db_session, setup, 0)
    assert saved.status_code == 200, saved.json()
    rosa = client.get(f"/leagues/{setup['league_id']}/rosa", headers=_headers(setup["tokens"][0]))
    assert rosa.json()["filledSlots"] == 35
    context = client.get(
        f"/leagues/{setup['league_id']}/turni/{setup['round_id']}/formazione",
        headers=_headers(setup["tokens"][0]),
    )
    assert "roster_not_validated" not in {item["code"] for item in context.json()["issues"]}

    # Il diritto è usato: un secondo acquisto è rifiutato.
    again = _buy(client, setup, 0, free_d[1])
    assert again.status_code == 400
    assert again.json()["code"] == "replacement_not_available"


def test_three_for_one_trade_gives_two_replacements_chosen_one_at_a_time(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.trexuno", id_offset=8_200_000)
    team_a = setup["teams"][0]
    free_d = _free_athletes(
        db_session, setup, role=FantasyRole.D, count=2, provider_offset=8_290_000, label="Liberi D"
    )
    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][:3],
        requested=setup["roles"][1][FantasyRole.C][:1],
    )
    assert [row.role for row in _rows(db_session, team_a)] == [FantasyRole.D, FantasyRole.D]
    status = _status(client, setup, 0)
    assert status["filledSlots"] == 33
    assert status["missingRoles"] == [{"role": "D", "count": 2}]

    first = _buy(client, setup, 0, free_d[0])
    assert first.status_code == 200, first.json()
    assert first.json()["status"]["missingRoles"] == [{"role": "D", "count": 1}]
    assert first.json()["status"]["filledSlots"] == 34
    assert _save_lineup(client, db_session, setup, 0).status_code == 400

    second = _buy(client, setup, 0, free_d[1])
    assert second.status_code == 200, second.json()
    assert second.json()["status"]["pending"] == []
    assert [row.status for row in _rows(db_session, team_a)] == [
        TradeReplacementStatus.CHOSEN,
        TradeReplacementStatus.CHOSEN,
    ]
    assert _save_lineup(client, db_session, setup, 0).status_code == 200


def test_replacement_purchase_refusals(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.rifiuti", id_offset=8_300_000)
    team_a, team_b = setup["teams"]
    free_d = _free_athletes(
        db_session, setup, role=FantasyRole.D, count=3, provider_offset=8_390_000, label="Rif D"
    )
    free_c = _free_athletes(
        db_session, setup, role=FantasyRole.C, count=1, provider_offset=8_391_000, label="Rif C"
    )
    # Senza scambio nessun diritto, nemmeno con la rosa incompleta (svincolo, rimozione admin).
    slot_b = next(
        slot
        for slot in _occupied(db_session, team_b)
        if slot.athlete_id == setup["roles"][1][FantasyRole.A][0]
    )
    slot_b.athlete_id = None
    slot_b.purchase_credits = None
    db_session.commit()
    no_right = _buy(client, setup, 1, free_d[0])
    assert no_right.status_code == 400
    assert no_right.json()["code"] == "replacement_not_available"
    assert _status(client, setup, 1)["pending"] == []

    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][:2],
        requested=setup["roles"][1][FantasyRole.C][:1],
    )
    assert len(_rows(db_session, team_a)) == 1
    # B era a 34 per altri motivi ed è a 35 dopo lo scambio: nessun diritto.
    assert _rows(db_session, team_b) == []

    wrong_role = _buy(client, setup, 0, free_c[0])
    assert wrong_role.status_code == 400
    assert wrong_role.json()["code"] == "replacement_wrong_role"
    assert "Difensore" in wrong_role.json()["message"]

    owned = setup["roles"][1][FantasyRole.D][0]
    taken = _buy(client, setup, 0, owned)
    assert taken.status_code == 400
    assert taken.json()["code"] == "athlete_already_owned"

    # Impegnato negli svincolati ancora aperti: non si può prendere.
    now = datetime.now(UTC)
    waiver = MarketSession(
        league_id=UUID(setup["league_id"]),
        kind=MarketSessionKind.WAIVER,
        status=MarketSessionStatus.OPEN,
        opens_at=now - timedelta(hours=1),
        closes_at=now + timedelta(hours=5),
    )
    db_session.add(waiver)
    db_session.flush()
    db_session.add(
        MarketBid(
            session_id=waiver.id,
            fantasy_team_id=UUID(team_b),
            athlete_id=free_d[1],
            amount_credits=5,
            release_athlete_id=setup["roles"][1][FantasyRole.D][1],
        )
    )
    db_session.commit()
    busy = _buy(client, setup, 0, free_d[1])
    assert busy.status_code == 400
    assert busy.json()["code"] == "athlete_in_open_auction"
    assert str(free_d[1]) not in {
        item["athleteId"] for item in _candidates(client, setup, 0)["candidates"]
    }

    # Crediti insufficienti: chi costa più del saldo è segnato e l'acquisto è rifiutato.
    price = _price(db_session, setup["league_id"], free_d[2])
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_a))
    )
    assert account is not None
    account.balance = price - 1
    db_session.commit()
    listing = _candidates(client, setup, 0, cerca="Rif D 2")
    assert [item["affordable"] for item in listing["candidates"]] == [False]
    poor = _buy(client, setup, 0, free_d[2])
    assert poor.status_code == 400
    assert poor.json()["code"] == "insufficient_credits"

    # Nessun rifiuto ha toccato rosa o diritto.
    assert len(_occupied(db_session, team_a)) == 34
    assert [row.status for row in _rows(db_session, team_a)] == [TradeReplacementStatus.PENDING]

    # L'operatore senza squadra (sola lettura) non compra.
    operator_token, operator_id = _register_and_login(client, "sost.rifiuti.op@example.com")
    operator = db_session.get(User, operator_id)
    assert operator is not None
    operator.platform_role = PlatformRole.OPERATOR
    db_session.commit()
    as_operator = client.post(
        f"/leagues/{setup['league_id']}/mercato/sostituti/acquista",
        headers=_headers(operator_token),
        json={"athleteId": str(free_d[2])},
    )
    assert as_operator.status_code == 400
    assert as_operator.json()["code"] == "membership_required"


def test_two_teams_on_the_same_free_agent_the_first_wins(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(
        client, db_session, competition_ids, prefix="sost.concorr", id_offset=8_400_000, teams=3
    )
    free_d = _free_athletes(
        db_session, setup, role=FantasyRole.D, count=1, provider_offset=8_490_000, label="Conteso"
    )
    # A e C cedono due difensori a B per un centrocampista: entrambi a 34, manca un D.
    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][:2],
        requested=setup["roles"][1][FantasyRole.C][:1],
    )
    _trade(
        client,
        setup,
        proposer=2,
        recipient=1,
        offered=setup["roles"][2][FantasyRole.D][:2],
        requested=setup["roles"][1][FantasyRole.C][1:2],
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_buy, client, setup, team, free_d[0]) for team in (0, 2)]
        responses = [future.result() for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 400]
    loser = next(response for response in responses if response.status_code == 400)
    assert loser.json()["code"] == "athlete_already_owned"
    assert "Conteso 0" in loser.json()["message"]
    owners = db_session.scalars(
        select(FantasyRosterSlot.fantasy_team_id).where(FantasyRosterSlot.athlete_id == free_d[0])
    ).all()
    assert len(owners) == 1


def test_open_replacement_is_cancelled_when_the_roster_is_completed_another_way(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.annulla", id_offset=8_500_000)
    team_a, team_b = setup["teams"]
    free_d = _free_athletes(
        db_session, setup, role=FantasyRole.D, count=1, provider_offset=8_590_000, label="Admin D"
    )
    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][:2],
        requested=setup["roles"][1][FantasyRole.C][:1],
    )
    assert [row.status for row in _rows(db_session, team_a)] == [TradeReplacementStatus.PENDING]

    # Scambio 1 per 2 a favore di A: torna a 35 e il diritto si chiude da solo.
    _trade(
        client,
        setup,
        proposer=1,
        recipient=0,
        offered=setup["roles"][0][FantasyRole.D][:2],  # i due difensori ricevuti prima
        requested=setup["roles"][0][FantasyRole.C][:1],
    )
    assert len(_occupied(db_session, team_a)) == 35
    rows = _rows(db_session, team_a)
    assert [row.status for row in rows] == [TradeReplacementStatus.CANCELLED]
    assert rows[0].cancelled_at is not None
    assert _rows(db_session, team_b) == []
    assert _status(client, setup, 0)["pending"] == []

    # Di nuovo corta; questa volta la completa l'assegnazione dell'admin.
    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][2:4],
        requested=setup["roles"][1][FantasyRole.C][1:2],
    )
    assert [row.status for row in _rows(db_session, team_a)][-1] == TradeReplacementStatus.PENDING
    free_slot = db_session.scalar(
        select(FantasyRosterSlot.slot_index)
        .where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_a),
            FantasyRosterSlot.athlete_id.is_(None),
        )
        .order_by(FantasyRosterSlot.slot_index.asc())
    )
    assigned = client.put(
        f"/leagues/{setup['league_id']}/amministrazione/squadre/{team_a}/slot/{free_slot}",
        headers=_headers(setup["tokens"][0]),
        json={"athleteId": str(free_d[0]), "purchaseCredits": 1},
    )
    assert assigned.status_code == 200, assigned.json()
    assert [row.status for row in _rows(db_session, team_a)][-1] == (
        TradeReplacementStatus.CANCELLED
    )


def test_proposals_show_the_roster_after_the_trade_to_proposer_recipient_and_admin(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(
        client, db_session, competition_ids, prefix="sost.avviso", id_offset=8_600_000, teams=3
    )
    rules = db_session.scalar(
        select(LeagueRules).where(LeagueRules.league_id == UUID(setup["league_id"]))
    )
    assert rules is not None
    rules.require_trade_approval = True
    db_session.commit()
    league_id = setup["league_id"]
    offered = setup["roles"][1][FantasyRole.D][:1] + setup["roles"][1][FantasyRole.C][:1]
    requested = setup["roles"][2][FantasyRole.A][:1]
    draft = {
        "recipientTeamId": setup["teams"][2],
        "offeredAthleteIds": [str(item) for item in offered],
        "requestedAthleteIds": [str(item) for item in requested],
    }

    # Chi propone vede l'avviso prima di inviare.
    preview = client.post(
        f"/leagues/{league_id}/mercato/scambi/anteprima",
        headers=_headers(setup["tokens"][1]),
        json=draft,
    )
    assert preview.status_code == 200, preview.json()
    mine = preview.json()["proposerRosterAfter"]
    assert mine["sizeAfter"] == 34
    assert mine["rosterSize"] == 35
    # Ceduti un D e un C per un A: un posto solo, il ruolo è quello del primo ceduto in più.
    assert mine["missingRoles"] == [{"role": "D", "count": 1}]
    other = preview.json()["recipientRosterAfter"]
    assert other["sizeAfter"] == 36
    assert other["missingRoles"] == []

    proposal = _trade(
        client, setup, proposer=1, recipient=2, offered=offered, requested=requested, accept=False
    )
    assert proposal["proposerRosterAfter"]["missingRoles"] == [{"role": "D", "count": 1}]
    assert proposal["proposerRosterAfter"]["teamId"] == setup["teams"][1]

    # Chi accetta vede l'avviso sulla rosa dell'altro (qui lui sale a 36).
    received = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte", headers=_headers(setup["tokens"][2])
    ).json()["proposals"]
    assert received[0]["recipientRosterAfter"]["missingRoles"] == []
    assert received[0]["proposerRosterAfter"]["sizeAfter"] == 34
    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers=_headers(setup["tokens"][2]),
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "pending_approval"
    # In attesa dell'admin non si muove nulla: nessun diritto ancora.
    assert _rows(db_session, setup["teams"][1]) == []

    # L'admin che approva vede le due rose, con il nome della squadra coinvolta.
    pending = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte", headers=_headers(setup["tokens"][0])
    ).json()["proposals"]
    target = next(item for item in pending if item["id"] == proposal["id"])
    assert target["proposerRosterAfter"]["teamName"]
    assert target["proposerRosterAfter"]["missingRoles"] == [{"role": "D", "count": 1}]

    approved = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/approva",
        headers=_headers(setup["tokens"][0]),
    )
    assert approved.status_code == 200, approved.json()
    assert approved.json()["status"] == "executed"
    assert approved.json()["proposerRosterAfter"] is None  # scambio chiuso: niente anteprima
    assert [row.role for row in _rows(db_session, setup["teams"][1])] == [FantasyRole.D]
    notified = db_session.scalars(
        select(Notification.user_id).where(
            Notification.template_key == "mercato.sostituto_scambio",
            Notification.user_id.in_(setup["user_ids"]),
        )
    ).all()
    assert notified == [setup["user_ids"][1]]


def test_replacement_waits_for_the_round_in_progress(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.turno", id_offset=8_700_000)
    free_d = _free_athletes(
        db_session, setup, role=FantasyRole.D, count=1, provider_offset=8_790_000, label="Turno D"
    )
    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][:2],
        requested=setup["roles"][1][FantasyRole.C][:1],
    )
    fantasy_round = db_session.get(FantasyRound, UUID(setup["round_id"]))
    assert fantasy_round is not None
    fantasy_round.cutoff_at = datetime.now(UTC) - timedelta(hours=1)
    fantasy_round.status = FantasyTurnStatus.LOCKED
    db_session.commit()

    status = _status(client, setup, 0)
    assert status["blockedReason"] == "round_in_progress"
    assert "turno 1" in status["blockedMessage"]
    refused = _buy(client, setup, 0, free_d[0])
    assert refused.status_code == 400
    assert refused.json()["code"] == "market_round_in_progress"
    assert refused.json()["message"] == status["blockedMessage"]
    assert "potrai scegliere il sostituto" in refused.json()["message"]
    assert [row.status for row in _rows(db_session, setup["teams"][0])] == [
        TradeReplacementStatus.PENDING
    ]
