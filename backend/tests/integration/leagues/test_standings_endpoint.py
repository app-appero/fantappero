"""Integration coverage for GET /leagues/{id}/classifica (EP07-06)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueMemberRole
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
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


def test_standings_are_computed_on_first_read_with_all_teams_at_zero(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "standings.owner@example.com")
    member_token, member_id = _register_and_login(client, "standings.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Classifica Iniziale")
    _add_member(db_session, league_id, member_id)

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ensured.status_code == 200
    # The owner's own team already exists from league creation; only the
    # newly added member's team is created here.
    assert ensured.json()["created"] == 1
    assert ensured.json()["existing"] == 1

    response = client.get(
        f"/leagues/{league_id}/classifica",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    for row in rows:
        assert row["played"] == 0
        assert row["won"] == 0
        assert row["drawn"] == 0
        assert row["lost"] == 0
        assert row["points"] == 0
        assert row["fantasyGoalsFor"] == 0
        assert row["fantasyGoalsAgainst"] == 0

    # Second read must not duplicate rows or recompute from scratch needlessly.
    again = client.get(
        f"/leagues/{league_id}/classifica",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert again.status_code == 200
    assert len(again.json()) == 2


def test_standings_endpoint_shows_solo_owner_team_at_zero_before_any_invite(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    """League creation already provisions the owner's own team; the
    classifica should reflect it immediately, before anyone else joins."""
    owner_token, _ = _register_and_login(client, "standings.soloowner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Solo Owner")

    response = client.get(
        f"/leagues/{league_id}/classifica",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["points"] == 0
    assert rows[0]["played"] == 0
