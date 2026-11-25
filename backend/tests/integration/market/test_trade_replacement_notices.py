"""Sostituto dopo uno scambio: avvisi su crediti e ruoli sotto quota (corsa Mercato, 25/11).

Solo dati in più per gli avvisi di sito e app, nessuna regola nuova:

- nella «rosa dopo lo scambio» i crediti dopo lo scambio (con quelli offerti o chiesti), il
  prezzo del libero più economico di ogni ruolo che manca (stesso prezzo e stessi liberi
  dell'acquisto) e un sì/no «può permettersi il sostituto»; lo scambio non si blocca;
- in ``GET …/mercato/sostituti`` lo stesso sì/no e il prezzo più basso;
- i ruoli sotto quota (ruolo, quanti, quota) dopo lo scambio e nella rosa di adesso (``GET
  …/rosa``, ``composition.underQuotaRoles``), anche con la rosa alla misura.

File a parte rispetto a ``test_trade_replacement.py``: ogni file ha il suo database pulito e lì
le partite accumulate dai test fanno già generare i turni alla creazione delle leghe nuove.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url
from tests.integration.market.test_trade_replacement import (
    _balance,
    _buy,
    _candidates,
    _free_athletes,
    _headers,
    _league,
    _rows,
    _status,
    _trade,
)

from database.enums import FantasyRole
from database.session import create_session_factory
from fantasy_teams.models import CreditAccount
from leagues.models.competition import Competition
from market.valuation_models import AthleteMarketValue
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


def _cheapest_value(db_session: Session, athlete_ids: list[UUID], role: FantasyRole) -> None:
    """Valore materializzato a zero: il loro prezzo è il minimo (1 credito), sotto ogni altro."""
    for athlete_id in athlete_ids:
        athlete = db_session.get(Athlete, athlete_id)
        assert athlete is not None
        db_session.add(
            AthleteMarketValue(
                athlete_id=athlete_id,
                athlete_provider_id=athlete.provider_id,
                season_year=2026,
                role=role,
                value_index=0.0,
                reference_value=0.0,
            )
        )
    db_session.commit()


def _set_balance(db_session: Session, team_id: str, balance: int) -> None:
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    account.balance = balance
    db_session.commit()


def _preview(
    client: TestClient,
    setup: dict,
    *,
    offered: list[UUID],
    requested: list[UUID],
    proposer: int = 0,
    recipient: int = 1,
    credits: dict[str, int] | None = None,
) -> dict:
    response = client.post(
        f"/leagues/{setup['league_id']}/mercato/scambi/anteprima",
        headers=_headers(setup["tokens"][proposer]),
        json={
            "recipientTeamId": setup["teams"][recipient],
            "offeredAthleteIds": [str(item) for item in offered],
            "requestedAthleteIds": [str(item) for item in requested],
            **(credits or {}),
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()


def _my_roster(client: TestClient, setup: dict, team: int) -> dict:
    response = client.get(
        f"/leagues/{setup['league_id']}/rosa", headers=_headers(setup["tokens"][team])
    )
    assert response.status_code == 200, response.json()
    return response.json()


def test_roster_after_the_trade_counts_the_credits_and_the_cheapest_free_player(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.crediti", id_offset=8_800_000)
    team_a, team_b = setup["teams"]
    free_d = _free_athletes(
        db_session, setup, role=FantasyRole.D, count=2, provider_offset=8_890_000, label="Econ D"
    )
    _cheapest_value(db_session, free_d, FantasyRole.D)
    offered = setup["roles"][0][FantasyRole.D][:2]
    requested = setup["roles"][1][FantasyRole.C][:1]
    balance_a = _balance(db_session, team_a)
    balance_b = _balance(db_session, team_b)

    # Chi propone offre 5 crediti: li conta nei suoi crediti dopo lo scambio e l'altro li riceve.
    offering = _preview(
        client, setup, offered=offered, requested=requested, credits={"offeredCredits": 5}
    )
    mine = offering["proposerRosterAfter"]
    # I campi di prima restano gli stessi.
    assert mine["teamId"] == team_a
    assert mine["sizeAfter"] == 34
    assert mine["rosterSize"] == 35
    assert mine["missingRoles"] == [{"role": "D", "count": 1}]
    assert mine["balanceAfter"] == balance_a - 5
    assert mine["replacementCosts"] == [
        {"role": "D", "count": 1, "cheapestPrice": 1, "totalPrice": 1}
    ]
    assert mine["canAffordReplacement"] is True
    other = offering["recipientRosterAfter"]
    assert other["sizeAfter"] == 36
    assert other["missingRoles"] == []
    assert other["balanceAfter"] == balance_b + 5
    assert other["replacementCosts"] == []
    assert other["canAffordReplacement"] is True

    # Crediti chiesti: al contrario.
    asking = _preview(
        client, setup, offered=offered, requested=requested, credits={"requestedCredits": 7}
    )
    assert asking["proposerRosterAfter"]["balanceAfter"] == balance_a + 7
    assert asking["recipientRosterAfter"]["balanceAfter"] == balance_b - 7

    # Con 4 crediti offerti su 4 resta a 0: il libero più economico (1) non è alla sua portata.
    _set_balance(db_session, team_a, 4)
    poor = _preview(
        client, setup, offered=offered, requested=requested, credits={"offeredCredits": 4}
    )["proposerRosterAfter"]
    assert poor["balanceAfter"] == 0
    assert poor["canAffordReplacement"] is False
    assert poor["replacementCosts"] == [
        {"role": "D", "count": 1, "cheapestPrice": 1, "totalPrice": 1}
    ]
    # Le app 1.4 non mandano i crediti: vale il saldo di adesso.
    legacy = _preview(client, setup, offered=offered, requested=requested)
    assert legacy["proposerRosterAfter"]["balanceAfter"] == 4

    # Tre per uno: due D da scegliere, i due liberi più economici insieme.
    three = _preview(
        client, setup, offered=setup["roles"][0][FantasyRole.D][:3], requested=requested
    )["proposerRosterAfter"]
    assert three["replacementCosts"] == [
        {"role": "D", "count": 2, "cheapestPrice": 1, "totalPrice": 2}
    ]
    assert three["canAffordReplacement"] is True

    # La proposta vera porta gli stessi dati, con i crediti offerti; lo scambio non si blocca.
    proposal = client.post(
        f"/leagues/{setup['league_id']}/mercato/scambi/proposte",
        headers=_headers(setup["tokens"][0]),
        json={
            "recipientTeamId": team_b,
            "offeredAthleteIds": [str(item) for item in offered],
            "requestedAthleteIds": [str(item) for item in requested],
            "offeredCredits": 4,
            "requestedCredits": 0,
        },
    )
    assert proposal.status_code == 201, proposal.json()
    assert proposal.json()["proposerRosterAfter"]["balanceAfter"] == 0
    assert proposal.json()["proposerRosterAfter"]["canAffordReplacement"] is False
    received = client.get(
        f"/leagues/{setup['league_id']}/mercato/scambi/proposte",
        headers=_headers(setup["tokens"][1]),
    ).json()["proposals"]
    target = next(item for item in received if item["id"] == proposal.json()["id"])
    assert target["recipientRosterAfter"]["balanceAfter"] == balance_b + 4
    assert target["proposerRosterAfter"]["canAffordReplacement"] is False
    accepted = client.post(
        f"/leagues/{setup['league_id']}/mercato/scambi/proposte/{target['id']}/accetta",
        headers=_headers(setup["tokens"][1]),
    )
    assert accepted.status_code == 200, accepted.json()
    assert [row.role for row in _rows(db_session, team_a)] == [FantasyRole.D]


def test_replacement_status_says_whether_the_cheapest_free_player_is_affordable(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.portata", id_offset=8_900_000)
    team_a = setup["teams"][0]
    _free_athletes(
        db_session, setup, role=FantasyRole.D, count=2, provider_offset=8_990_000, label="Port D"
    )
    _trade(
        client,
        setup,
        proposer=0,
        recipient=1,
        offered=setup["roles"][0][FantasyRole.D][:2],
        requested=setup["roles"][1][FantasyRole.C][:1],
    )
    _set_balance(db_session, team_a, 0)
    status = _status(client, setup, 0)
    # I campi di prima restano gli stessi.
    assert status["filledSlots"] == 34
    assert status["balance"] == 0
    assert status["missingRoles"] == [{"role": "D", "count": 1}]
    assert len(status["pending"]) == 1
    # Il prezzo più basso è quello dell'elenco dei liberi (stesse regole dell'acquisto).
    listing = _candidates(client, setup, 0, ordine="valore-crescente")["candidates"]
    cheapest = listing[0]["marketValue"]
    assert status["cheapestReplacementPrice"] == cheapest
    assert status["replacementCosts"] == [
        {"role": "D", "count": 1, "cheapestPrice": cheapest, "totalPrice": cheapest}
    ]
    assert status["canAffordReplacement"] is False
    assert not any(item["affordable"] for item in listing)

    _set_balance(db_session, team_a, cheapest)
    assert _status(client, setup, 0)["canAffordReplacement"] is True

    # Senza sostituti da scegliere: nessun prezzo, nessun avviso.
    other = _status(client, setup, 1)
    assert other["pending"] == []
    assert other["canAffordReplacement"] is True
    assert other["cheapestReplacementPrice"] is None
    assert other["replacementCosts"] == []


def test_one_for_one_between_roles_leaves_a_role_under_quota_with_the_roster_full(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.quota", id_offset=9_000_000)
    team_a = setup["teams"][0]
    offered = setup["roles"][0][FantasyRole.C][:1]
    requested = setup["roles"][1][FantasyRole.D][:1]
    assert _my_roster(client, setup, 0)["composition"]["underQuotaRoles"] == []

    # A cede un C e riceve un D: resta 35/35, ma con 10 Centrocampisti su 11.
    preview = _preview(client, setup, offered=offered, requested=requested)
    mine = preview["proposerRosterAfter"]
    assert mine["sizeAfter"] == 35
    assert mine["missingRoles"] == []
    assert mine["replacementCosts"] == []
    assert mine["canAffordReplacement"] is True
    assert mine["underQuotaRoles"] == [{"role": "C", "count": 10, "quota": 11}]
    assert preview["recipientRosterAfter"]["underQuotaRoles"] == [
        {"role": "D", "count": 10, "quota": 11}
    ]

    _trade(client, setup, proposer=0, recipient=1, offered=offered, requested=requested)
    # Nessuna regola cambia: rosa alla misura, nessun sostituto.
    assert _rows(db_session, team_a) == []
    rosa = _my_roster(client, setup, 0)
    assert rosa["filledSlots"] == 35
    assert rosa["composition"]["underQuotaRoles"] == [{"role": "C", "count": 10, "quota": 11}]
    status = _status(client, setup, 0)
    assert status["pending"] == []
    assert status["underQuotaRoles"] == [{"role": "C", "count": 10, "quota": 11}]


def test_after_the_last_replacement_the_status_tells_the_role_still_under_quota(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _league(client, db_session, competition_ids, prefix="sost.ultimo", id_offset=9_100_000)
    free_c = _free_athletes(
        db_session, setup, role=FantasyRole.C, count=1, provider_offset=9_190_000, label="Ult C"
    )
    offered = setup["roles"][0][FantasyRole.C][:2]
    requested = setup["roles"][1][FantasyRole.D][:1]
    # Due C per un D: 34/35, manca un C; anche con il sostituto i C restano 10 su 11.
    before = _preview(client, setup, offered=offered, requested=requested)["proposerRosterAfter"]
    assert before["missingRoles"] == [{"role": "C", "count": 1}]
    assert before["underQuotaRoles"] == [{"role": "C", "count": 9, "quota": 11}]

    _trade(client, setup, proposer=0, recipient=1, offered=offered, requested=requested)
    status = _status(client, setup, 0)
    assert status["missingRoles"] == [{"role": "C", "count": 1}]
    assert status["underQuotaRoles"] == [{"role": "C", "count": 9, "quota": 11}]

    bought = _buy(client, setup, 0, free_c[0])
    assert bought.status_code == 200, bought.json()
    after = bought.json()["status"]
    assert after["pending"] == []
    assert after["filledSlots"] == 35
    assert after["underQuotaRoles"] == [{"role": "C", "count": 10, "quota": 11}]
    assert _my_roster(client, setup, 0)["composition"]["underQuotaRoles"] == [
        {"role": "C", "count": 10, "quota": 11}
    ]
