"""Integration tests for the admin-controlled market window (rosa/asta vs scambi)."""

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
    body = response.json()
    assert body["marketOpen"] is True
    return body["id"]


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
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole = FantasyRole.D,
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


def _own_athlete_at_slot(
    client: TestClient, league_id: str, token: str, slot_index: int, athlete: Athlete
) -> str:
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()
    team_id = rosa["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 1},
    )
    assert response.status_code == 200
    return team_id


def test_admin_toggles_market_gate_member_cannot(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, _ = _register_and_login(client, "gate.admin@example.com")
    member_token, member_id = _register_and_login(client, "gate.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Interruttore")
    _add_member(db_session, league_id, member_id)

    opened = client.get(
        f"/leagues/{league_id}/mercato/stato",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert opened.status_code == 200
    assert opened.json()["marketOpen"] is True

    forbidden = client.post(
        f"/leagues/{league_id}/mercato/stato",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"open": False},
    )
    assert forbidden.status_code in {403, 400}

    closed = client.post(
        f"/leagues/{league_id}/mercato/stato",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"open": False},
    )
    assert closed.status_code == 200
    assert closed.json()["marketOpen"] is False

    listing = client.get("/leagues/mine", headers={"Authorization": f"Bearer {admin_token}"})
    assert listing.status_code == 200
    row = next(item for item in listing.json() if item["id"] == league_id)
    assert row["marketOpen"] is False

    reopened = client.post(
        f"/leagues/{league_id}/mercato/stato",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"open": True},
    )
    assert reopened.status_code == 200
    assert reopened.json()["marketOpen"] is True


def test_closed_market_blocks_roster_and_auction_but_allows_trades(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, _ = _register_and_login(client, "gate.moves.admin@example.com")
    member_token, member_id = _register_and_login(client, "gate.moves.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Finestra")
    _add_member(db_session, league_id, member_id)

    proposer_athlete = _seed_athlete(db_session, 9601, "Calciatore Admin")
    recipient_athlete = _seed_athlete(db_session, 9602, "Calciatore Membro")
    extra_athlete = _seed_athlete(db_session, 9603, "Calciatore Libero")

    admin_team_id = _own_athlete_at_slot(client, league_id, admin_token, 0, proposer_athlete)
    member_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, recipient_athlete)

    closed = client.post(
        f"/leagues/{league_id}/mercato/stato",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"open": False},
    )
    assert closed.status_code == 200

    blocked_assign = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{admin_team_id}/slot/1",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(extra_athlete.id), "purchaseCredits": 1},
    )
    assert blocked_assign.status_code == 400
    assert blocked_assign.json()["code"] == "market_closed"

    blocked_release = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{admin_team_id}/slot/0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert blocked_release.status_code == 400
    assert blocked_release.json()["code"] == "market_closed"

    opens_at = datetime.now(UTC).isoformat()
    closes_at = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
    blocked_auction = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"opensAt": opens_at, "closesAt": closes_at},
    )
    assert blocked_auction.status_code == 400
    assert blocked_auction.json()["code"] == "market_closed"

    blocked_live = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": opens_at,
            "closesAt": closes_at,
            "nominationMode": "manual",
            "minIncrementCredits": 10,
            "softCloseSeconds": 5,
            "lotDurationSeconds": 30,
        },
    )
    assert blocked_live.status_code == 400
    assert blocked_live.json()["code"] == "market_closed"

    trade = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": member_team_id,
            "offeredAthleteIds": [str(proposer_athlete.id)],
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "offeredCredits": 0,
            "requestedCredits": 0,
            "expiresAt": None,
        },
    )
    assert trade.status_code == 201
    assert trade.json()["status"] in {"proposed", "pending_approval"}
