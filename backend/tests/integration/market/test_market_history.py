"""Integration tests for the market history feed (EP08-08 / FR-MKT-04)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueMemberRole
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
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


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(db_session: Session, league_id: str, user_id: UUID) -> LeagueMembership:
    membership = LeagueMembership(
        league_id=UUID(league_id),
        user_id=user_id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


def _seed_athlete(
    db_session: Session, provider_id: int, name: str, *, season_year: int = 2026
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=FantasyRole.D,
            mapping_version="v1.0.0",
            provider_position_raw=FantasyRole.D.value,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _team_id(client: TestClient, league_id: str, token: str) -> str:
    return client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]


def _own_athlete_at_slot(
    client: TestClient, league_id: str, token: str, slot_index: int, athlete: Athlete
) -> str:
    team_id = _team_id(client, league_id, token)
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 200
    return team_id


def _create_open_session(client: TestClient, admin_token: str, league_id: str) -> str:
    now = datetime.now(UTC)
    response = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(minutes=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _bid(client: TestClient, league_id: str, session_id: str, token: str, athlete_id, amount: int):
    return client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"amountCredits": amount},
    )


def _close_and_resolve(client: TestClient, league_id: str, session_id: str, admin_token: str):
    close = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert close.status_code == 200
    return client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _history(client: TestClient, league_id: str, token: str, **params):
    return client.get(
        f"/leagues/{league_id}/mercato/storico",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )


def test_history_is_empty_for_a_league_with_no_market_activity(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, _ = _register_and_login(client, "hist.empty.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Vuoto")

    response = _history(client, league_id, admin_token)
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "page": 1, "pageSize": 20, "total": 0, "totalPages": 0}


def test_history_shows_auction_resolution_as_acquisto_with_winner(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.auction.admin@example.com")
    member_token, member_id = _register_and_login(client, "hist.auction.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Asta")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9801, "Giocatore Storico Asta")

    admin_team_id = _team_id(client, league_id, admin_token)
    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete.id, 200).status_code == 200
    assert _bid(client, league_id, session_id, member_token, athlete.id, 150).status_code == 200
    resolution = _close_and_resolve(client, league_id, session_id, admin_token)
    assert resolution.status_code == 200

    all_history = _history(client, league_id, admin_token).json()
    resolved_entries = [
        item for item in all_history["items"] if item["action"] == "market_session_resolved"
    ]
    assert len(resolved_entries) == 1
    winners = resolved_entries[0]["details"]["winners"]
    assert winners == [
        {"fantasyTeamId": admin_team_id, "athleteId": str(athlete.id), "amountCredits": 200}
    ]
    assert resolved_entries[0]["category"] == "acquisto"

    only_acquisti = _history(client, league_id, admin_token, category="acquisto").json()
    assert all(item["category"] == "acquisto" for item in only_acquisti["items"])
    assert any(item["action"] == "market_session_created" for item in only_acquisti["items"])

    only_scambi = _history(client, league_id, admin_token, category="scambio").json()
    assert only_scambi["items"] == []


def test_history_filters_by_fantasy_team_id(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.team.admin@example.com")
    member_token, member_id = _register_and_login(client, "hist.team.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Squadra")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9802, "Giocatore Storico Squadra")

    admin_team_id = _team_id(client, league_id, admin_token)
    member_team_id = _team_id(client, league_id, member_token)
    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete.id, 300).status_code == 200
    assert _bid(client, league_id, session_id, member_token, athlete.id, 100).status_code == 200
    assert _close_and_resolve(client, league_id, session_id, admin_token).status_code == 200

    winner_history = _history(
        client, league_id, admin_token, fantasyTeamId=admin_team_id
    ).json()
    assert any(
        item["action"] == "market_session_resolved" for item in winner_history["items"]
    )
    assert any(item["action"] == "market_bid_submitted" for item in winner_history["items"])

    loser_history = _history(
        client, league_id, admin_token, fantasyTeamId=member_team_id
    ).json()
    assert not any(
        item["action"] == "market_session_resolved" for item in loser_history["items"]
    )
    assert any(item["action"] == "market_bid_submitted" for item in loser_history["items"])


def test_history_shows_voluntary_release_as_svincolo(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.release.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Svincolo")
    athlete = _seed_athlete(db_session, 9803, "Giocatore Storico Svincolo")
    _own_athlete_at_slot(client, league_id, admin_token, 0, athlete)

    release = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "voluntary"},
    )
    assert release.status_code == 200

    history = _history(client, league_id, admin_token, category="svincolo").json()
    assert len(history["items"]) == 1
    entry = history["items"][0]
    assert entry["action"] == "fantasy_roster_slot_released"
    assert entry["details"]["reason"] == "voluntary"
    assert entry["details"]["athleteId"] == str(athlete.id)


def test_history_shows_executed_trade_as_scambio(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.trade.admin@example.com")
    member_token, member_id = _register_and_login(client, "hist.trade.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Scambio")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9804, "Giocatore Storico Scambio")
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, athlete)

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 20,
            "requestedAthleteIds": [str(athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()
    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    history = _history(client, league_id, admin_token, category="scambio").json()
    actions = {item["action"] for item in history["items"]}
    assert actions == {"market_trade_proposed", "market_trade_accepted"}
    for item in history["items"]:
        assert item["details"]["proposalId"] == proposal["id"]

    proposer_only = _history(
        client, league_id, admin_token, category="scambio", fantasyTeamId=recipient_team_id
    ).json()
    assert len(proposer_only["items"]) == 2


def test_history_shows_admin_credit_adjustment_as_intervento_manuale(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.credit.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Crediti")
    team_id = _team_id(client, league_id, admin_token)

    movement = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "fantasyTeamId": team_id,
            "amount": 25,
            "transactionId": "hist-credit-adjustment-1",
            "note": "Correzione manuale",
        },
    )
    assert movement.status_code == 200

    history = _history(client, league_id, admin_token, category="intervento_manuale").json()
    assert len(history["items"]) == 1
    entry = history["items"][0]
    assert entry["action"] == "credit_ledger_entry_posted"
    assert entry["details"]["fantasyTeamId"] == team_id
    assert entry["details"]["amount"] == 25


def test_history_pagination(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.page.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Paginazione")
    athlete_one = _seed_athlete(db_session, 9805, "Giocatore Pagina Uno")
    athlete_two = _seed_athlete(db_session, 9806, "Giocatore Pagina Due")

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete_one.id, 50).status_code == 200
    assert _bid(client, league_id, session_id, admin_token, athlete_two.id, 60).status_code == 200
    # session created + 2 bids submitted = 3 acquisto events so far.

    page_one = _history(client, league_id, admin_token, page=1, pageSize=2).json()
    assert page_one["page"] == 1
    assert page_one["pageSize"] == 2
    assert page_one["total"] == 3
    assert page_one["totalPages"] == 2
    assert len(page_one["items"]) == 2

    page_two = _history(client, league_id, admin_token, page=2, pageSize=2).json()
    assert len(page_two["items"]) == 1

    seen_ids = {item["id"] for item in page_one["items"]} | {item["id"] for item in page_two["items"]}
    assert len(seen_ids) == 3


def test_history_rejects_invalid_category(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.invalid.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Categoria")

    response = _history(client, league_id, admin_token, category="non_esistente")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_history_category"


def test_history_requires_league_membership(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "hist.outsider.admin@example.com")
    outsider_token, outsider_id = _register_and_login(client, "hist.outsider.other@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Storico Permessi")

    response = _history(client, league_id, outsider_token)
    assert response.status_code == 403
