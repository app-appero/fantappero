"""Integration tests for the sealed-bid waiver window (EP08-03 / FR-MKT-01)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import CreditLedgerReason, FantasyRole
from database.session import create_session_factory
from fantasy_teams.models import CreditAccount, CreditLedgerEntry, FantasyRosterSlot
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


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


_OWNER_TOKENS: dict[str, str] = {}


def _owner_headers(league_id: str, fallback_token: str) -> dict[str, str]:
    """N12: solo l'amministratore assegna calciatori a mano; i test lo fanno a suo nome."""
    return {"Authorization": f"Bearer {_OWNER_TOKENS.get(league_id, fallback_token)}"}


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    _OWNER_TOKENS[response.json()["id"]] = token
    return response.json()["id"]


def _seed_athlete(
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole = FantasyRole.A,
    season_year: int = 2026,
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _own_first_athlete_on_roster(
    client: TestClient, db_session: Session, league_id: str, token: str, athlete: Athlete
) -> str:
    """Fill the caller's slot 0 with ``athlete`` for free; returns the fantasy team id."""
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert rosa["filledSlots"] == 0  # sanity: roster started empty
    team_id = rosa["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers=_owner_headers(league_id, token),
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 200
    return team_id


def _create_open_waiver_session(client: TestClient, admin_token: str, league_id: str) -> str:
    now = datetime.now(UTC)
    response = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(minutes=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "open"
    return response.json()["id"]


def test_waiver_bid_requires_release_athlete_owned_by_team(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "waiver.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Svincoli")
    free_agent = _seed_athlete(db_session, 9301, "Svincolato Libero")
    owned = _seed_athlete(db_session, 9302, "Giocatore Posseduto", role=FantasyRole.D)
    _own_first_athlete_on_roster(client, db_session, league_id, admin_token, owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)

    missing_release = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50},
    )
    assert missing_release.status_code == 400
    assert missing_release.json()["code"] == "release_athlete_required"

    not_owned = _seed_athlete(db_session, 9303, "Non Mio", role=FantasyRole.D)
    wrong_release = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50, "releaseAthleteId": str(not_owned.id)},
    )
    assert wrong_release.status_code == 400
    assert wrong_release.json()["code"] == "release_athlete_not_owned"

    ok = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50, "releaseAthleteId": str(owned.id)},
    )
    assert ok.status_code == 200
    assert ok.json()["releaseAthleteId"] == str(owned.id)
    assert ok.json()["releaseAthleteName"] == "Giocatore Posseduto"


def test_auction_bid_rejects_release_athlete_id(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "waiver.auction.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Vs Svincoli")
    athlete = _seed_athlete(db_session, 9304, "Libero Asta")
    now = datetime.now(UTC)
    session_resp = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(minutes=1)).isoformat(),
        },
    )
    session_id = session_resp.json()["id"]

    rejected = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 50, "releaseAthleteId": str(athlete.id)},
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "release_athlete_not_allowed"


def test_waiver_resolution_swaps_players_with_no_refund(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "waiver.swap.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Svincoli")
    free_agent = _seed_athlete(db_session, 9305, "Nuovo Acquisto", role=FantasyRole.D)
    owned = _seed_athlete(db_session, 9306, "Vecchio Giocatore", role=FantasyRole.D)
    team_id = _own_first_athlete_on_roster(client, db_session, league_id, admin_token, owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)
    bid = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 80, "releaseAthleteId": str(owned.id)},
    )
    assert bid.status_code == 200

    client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolution = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "assigned"
    assert outcome["amountCredits"] == 80

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is not None
    assert slot.athlete_id == free_agent.id
    assert slot.purchase_credits == 80

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == slot.fantasy_team_id)
    )
    assert account is not None
    assert account.balance == 1000 - 80  # no refund for the released player (EP08-04 scope)

    ledger_entry = db_session.scalar(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_WAIVER_ACQUISITION,
        )
    )
    assert ledger_entry is not None
    assert ledger_entry.amount == -80


def test_waiver_bid_lost_when_release_athlete_no_longer_owned(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """If the named release athlete leaves the roster before resolution, the bid loses
    instead of corrupting the roster ("cambio annullato se crea rosa invalida")."""
    admin_token, admin_id = _register_and_login(client, "waiver.stale.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Svincolo Obsoleto")
    free_agent = _seed_athlete(db_session, 9307, "Obsoleto Target", role=FantasyRole.D)
    owned = _seed_athlete(db_session, 9308, "Rilasciato Prima", role=FantasyRole.D)
    team_id = _own_first_athlete_on_roster(client, db_session, league_id, admin_token, owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)
    bid = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 60, "releaseAthleteId": str(owned.id)},
    )
    assert bid.status_code == 200

    # The team releases that same player manually before the waiver resolves.
    release = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert release.status_code == 200

    client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolution = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "unassigned"

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is not None
    assert slot.athlete_id is None  # untouched by the failed waiver, still empty from the release


def test_concurrent_waiver_resolve_calls_swap_exactly_once(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """B5: risolvere una sessione svincoli condivide lo stesso metodo/lock
    dell'asta (`resolve_session`: lock su MarketSession + `.with_for_update()`
    sulle offerte), già provato in test_auction_resolution.py per l'asta. Qui
    lo verifichiamo direttamente sul ramo svincoli, che in più scambia uno
    slot occupato invece di limitarsi ad assegnarne uno libero — non basta
    la parentela di codice come prova.
    """
    admin_token, admin_id = _register_and_login(client, "waiver.conc.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Concorrenza Svincoli")
    free_agent = _seed_athlete(db_session, 9309, "Concorrente Svincolato", role=FantasyRole.D)
    owned = _seed_athlete(db_session, 9310, "Concorrente Posseduto", role=FantasyRole.D)
    team_id = _own_first_athlete_on_roster(client, db_session, league_id, admin_token, owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)
    bid = client.put(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 70, "releaseAthleteId": str(owned.id)},
    )
    assert bid.status_code == 200
    client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    def _resolve(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/risolvi",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(_resolve, range(4)))

    assert all(status == 200 for status in statuses)

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is not None
    assert slot.athlete_id == free_agent.id
    assert slot.purchase_credits == 70

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    assert account.balance == 1000 - 70  # addebitato una sola volta, non una per thread

    ledger_entries = db_session.scalars(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_WAIVER_ACQUISITION,
        )
    ).all()
    assert len(ledger_entries) == 1


def test_waiver_bid_rejected_when_swap_would_exceed_role_quota(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Portieri al completo: svincolare un difensore per un portiere non può mai riuscire."""
    import random

    admin_token, _ = _register_and_login(client, "waiver.quota.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Svincoli Quota")
    team_id = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {admin_token}"}
    ).json()["id"]
    base = random.randint(100_000_000, 2_000_000_000)
    owned = [
        _seed_athlete(db_session, base + index, f"Portiere {index}", role=FantasyRole.P)
        for index in range(3)
    ]
    defender = _seed_athlete(db_session, base + 10, "Difensore Da Svincolare", role=FantasyRole.D)
    for index, athlete in enumerate([*owned, defender]):
        placed = client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{index}",
            headers=_owner_headers(league_id, admin_token),
            json={"athleteId": str(athlete.id), "purchaseCredits": 0},
        )
        assert placed.status_code == 200, placed.text
    fourth_keeper = _seed_athlete(db_session, base + 20, "Quarto Portiere", role=FantasyRole.P)

    session_id = _create_open_waiver_session(client, admin_token, league_id)
    url = f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{fourth_keeper.id}"
    headers = {"Authorization": f"Bearer {admin_token}"}

    over = client.put(
        url, headers=headers, json={"amountCredits": 10, "releaseAthleteId": str(defender.id)}
    )
    assert over.status_code == 400
    assert over.json()["code"] == "waiver_role_quota_exceeded"

    same_role = client.put(
        url, headers=headers, json={"amountCredits": 10, "releaseAthleteId": str(owned[0].id)}
    )
    assert same_role.status_code == 200, same_role.text


def _add_league_member(db_session: Session, league_id: str, user_id: UUID) -> None:
    from database.enums import LeagueMemberRole
    from leagues.models.league_membership import LeagueMembership

    db_session.add(
        LeagueMembership(league_id=UUID(league_id), user_id=user_id, role=LeagueMemberRole.MEMBER)
    )
    db_session.commit()


def _waiver_outcome_notifications(db_session: Session, user_id: UUID) -> list:
    from notifications.models import Notification

    db_session.expire_all()
    return list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.template_key == "mercato.esito_busta",
            )
        ).all()
    )


def _two_teams_bid_on_same_free_agent(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    prefix: str,
    admin_amount: int,
    member_amount: int,
) -> dict:
    """Due squadre offrono per lo stesso svincolato; la sessione si chiude e si risolve."""
    import random

    admin_token, admin_id = _register_and_login(client, f"{prefix}.admin@example.com")
    member_token, member_id = _register_and_login(client, f"{prefix}.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, f"Lega {prefix}")
    _add_league_member(db_session, league_id, member_id)

    base = random.randint(100_000_000, 2_000_000_000)
    free_agent = _seed_athlete(db_session, base, "Svincolato Conteso", role=FantasyRole.D)
    admin_owned = _seed_athlete(db_session, base + 1, "Da Svincolare Uno", role=FantasyRole.D)
    member_owned = _seed_athlete(db_session, base + 2, "Da Svincolare Due", role=FantasyRole.D)
    admin_team = _own_first_athlete_on_roster(
        client, db_session, league_id, admin_token, admin_owned
    )
    _own_first_athlete_on_roster(client, db_session, league_id, member_token, member_owned)

    session_id = _create_open_waiver_session(client, admin_token, league_id)
    url = f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{free_agent.id}"
    for token, amount, release in (
        (admin_token, admin_amount, admin_owned),
        (member_token, member_amount, member_owned),
    ):
        bid = client.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"amountCredits": amount, "releaseAthleteId": str(release.id)},
        )
        assert bid.status_code == 200, bid.text
    client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolution = client.post(
        f"/leagues/{league_id}/mercato/svincoli/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolution.status_code == 200, resolution.text
    return {
        "league_id": league_id,
        "admin_token": admin_token,
        "admin_id": admin_id,
        "admin_team": admin_team,
        "member_id": member_id,
        "free_agent_id": free_agent.id,
        "outcome": resolution.json()["outcomes"][0],
    }


def test_waiver_results_use_waiver_titles_and_open_the_waiver_page(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 19-20/11: gli esiti degli svincolati arrivavano come «Busta aggiudicata» con il
    link all'asta. Ora hanno titoli e testi propri e aprono la pagina degli svincolati."""
    run = _two_teams_bid_on_same_free_agent(
        client,
        db_session,
        competition_ids,
        prefix="waiver.notify",
        admin_amount=80,
        member_amount=50,
    )
    league_id = run["league_id"]
    assert run["outcome"]["outcome"] == "assigned"

    won = _waiver_outcome_notifications(db_session, run["admin_id"])
    assert len(won) == 1
    assert won[0].title == "Svincolato aggiudicato"
    assert won[0].body.endswith(
        "Hai aggiudicato Svincolato Conteso dagli svincolati per 80 crediti."
    )
    assert won[0].deep_link == f"/svincolati?lega={league_id}"

    lost = _waiver_outcome_notifications(db_session, run["member_id"])
    assert len(lost) == 1
    assert lost[0].title == "Svincolato perso"
    assert lost[0].body.endswith(
        "Non hai aggiudicato Svincolato Conteso dagli svincolati: offerta inferiore."
    )
    assert lost[0].deep_link == f"/svincolati?lega={league_id}"


def test_waiver_tie_announces_a_waiver_tiebreak_and_its_cancellation(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Parità negli svincolati: lo spareggio si annuncia come spareggio degli svincolati.
    Se nel frattempo l'amministratore dà il calciatore a una delle due squadre, l'altra
    riceve «Spareggio svincolati annullato», sempre con il link agli svincolati."""
    run = _two_teams_bid_on_same_free_agent(
        client,
        db_session,
        competition_ids,
        prefix="waiver.tie",
        admin_amount=60,
        member_amount=60,
    )
    league_id = run["league_id"]
    assert run["outcome"]["outcome"] == "tiebreak"
    for user_id in (run["admin_id"], run["member_id"]):
        rows = _waiver_outcome_notifications(db_session, user_id)
        assert len(rows) == 1
        assert rows[0].title == "Spareggio svincolati aperto"
        assert "Parità su Svincolato Conteso negli svincolati" in rows[0].body
        assert rows[0].deep_link == f"/svincolati?lega={league_id}"

    admin_headers = {"Authorization": f"Bearer {run['admin_token']}"}
    placed = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{run['admin_team']}/slot/1",
        headers=admin_headers,
        json={"athleteId": str(run["free_agent_id"]), "purchaseCredits": 0},
    )
    assert placed.status_code == 200, placed.text
    tiebreak_id = run["outcome"]["tiebreakSessionId"]
    base = f"/leagues/{league_id}/mercato/svincoli/sessioni/{tiebreak_id}"
    assert client.post(f"{base}/chiudi", headers=admin_headers).status_code == 200
    assert client.post(f"{base}/risolvi", headers=admin_headers).status_code == 200

    cancelled = [
        row
        for row in _waiver_outcome_notifications(db_session, run["member_id"])
        if row.title == "Spareggio svincolati annullato"
    ]
    assert len(cancelled) == 1
    assert "Lo spareggio degli svincolati su Svincolato Conteso è annullato" in cancelled[0].body
    assert cancelled[0].deep_link == f"/svincolati?lega={league_id}"
    # Chi ora ha il calciatore non riceve l'annullamento.
    assert [row.title for row in _waiver_outcome_notifications(db_session, run["admin_id"])] == [
        "Spareggio svincolati aperto"
    ]
