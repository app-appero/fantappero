"""Integration tests for roster ownership history and turn snapshots (EP05-06)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import RosterOwnershipInterval, RosterTurnSnapshot
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
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


def _create_league(
    client: TestClient,
    token: str,
    competition_ids: list[str],
    name: str,
) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
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


def test_ownership_history_survives_release_and_as_of_reconstruction(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "hist.owner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Storico")
    athlete = _seed_athlete(db_session, provider_id=910001, name="Storico Attaccante")

    rosa = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]

    before_assign = datetime.now(UTC) - timedelta(seconds=1)
    assigned = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 15},
    )
    assert assigned.status_code == 200

    history = client.get(
        f"/leagues/{league_id}/rosa/storico",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert history.status_code == 200
    intervals = history.json()["intervals"]
    assert len(intervals) == 1
    assert intervals[0]["athleteId"] == str(athlete.id)
    assert intervals[0]["active"] is True
    assert intervals[0]["purchaseCredits"] == 15

    mid = datetime.now(UTC)
    released = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert released.status_code == 200
    assert released.json()["filledSlots"] == 0

    history_after = client.get(
        f"/leagues/{league_id}/rosa/storico",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert history_after.status_code == 200
    intervals_after = history_after.json()["intervals"]
    assert len(intervals_after) == 1
    assert intervals_after[0]["active"] is False
    assert intervals_after[0]["releasedAt"] is not None

    as_of_mid = client.get(
        f"/leagues/{league_id}/rosa/as-of",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"at": mid.isoformat()},
    )
    assert as_of_mid.status_code == 200
    assert as_of_mid.json()["filledSlots"] == 1
    assert as_of_mid.json()["slots"][0]["athleteId"] == str(athlete.id)

    as_of_before = client.get(
        f"/leagues/{league_id}/rosa/as-of",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"at": before_assign.isoformat()},
    )
    assert as_of_before.status_code == 200
    assert as_of_before.json()["filledSlots"] == 0

    closed_count = db_session.scalar(
        select(func.count(RosterOwnershipInterval.id)).where(
            RosterOwnershipInterval.league_id == UUID(league_id),
            RosterOwnershipInterval.released_at.is_not(None),
        )
    )
    assert closed_count == 1

    audit_closed = db_session.scalar(
        select(func.count(LeagueAuditEvent.id)).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROSTER_OWNERSHIP_CLOSED,
        )
    )
    assert audit_closed == 1


def test_turn_snapshot_idempotent_and_survives_release(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "snap.owner@example.com")
    member_token, member_id = _register_and_login(client, "snap.member@example.com")
    outsider_token, _ = _register_and_login(client, "snap.out@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Snapshot")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, provider_id=910002, name="Snapshot Player")

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ensured.status_code == 200
    team_id = ensured.json()["teams"][0]["id"]

    assigned = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 8},
    )
    assert assigned.status_code == 200

    created = client.post(
        f"/leagues/{league_id}/amministrazione/rosa/snapshot-turni",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"roundNumber": 1},
    )
    assert created.status_code == 200
    assert created.json()["created"] is True
    assert created.json()["roundNumber"] == 1
    assert created.json()["entryCount"] >= 1
    snapshot_id = created.json()["id"]

    again = client.post(
        f"/leagues/{league_id}/amministrazione/rosa/snapshot-turni",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"roundNumber": 1},
    )
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["id"] == snapshot_id

    client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    detail = client.get(
        f"/leagues/{league_id}/rosa/snapshot-turni/1",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["entryCount"] >= 1
    assert any(entry["athleteId"] == str(athlete.id) for entry in detail.json()["entries"])

    forbidden = client.post(
        f"/leagues/{league_id}/amministrazione/rosa/snapshot-turni",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"roundNumber": 2},
    )
    assert forbidden.status_code == 403

    outsider = client.get(
        f"/leagues/{league_id}/rosa/snapshot-turni",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert outsider.status_code == 403

    invalid = client.post(
        f"/leagues/{league_id}/amministrazione/rosa/snapshot-turni",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"roundNumber": 0},
    )
    assert invalid.status_code == 422

    db_count = db_session.scalar(
        select(func.count(RosterTurnSnapshot.id)).where(
            RosterTurnSnapshot.league_id == UUID(league_id)
        )
    )
    assert db_count == 1

    audit = db_session.scalar(
        select(func.count(LeagueAuditEvent.id)).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROSTER_TURN_SNAPSHOT_CREATED,
        )
    )
    assert audit == 1


def test_active_ownership_unique_under_concurrent_assign(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    owner_token, _ = _register_and_login(client, "hist.conc.owner@example.com")
    _, member_id = _register_and_login(client, "hist.conc.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Conc Hist")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, provider_id=910003, name="Race Hist")

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ensured.status_code == 200
    team_a = ensured.json()["teams"][0]["id"]
    team_b = ensured.json()["teams"][1]["id"]

    def _assign(team_id: str) -> int:
        response = client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/2",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"athleteId": str(athlete.id), "purchaseCredits": 1},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(_assign, [team_a, team_b]))

    assert statuses.count(200) == 1
    active = db_session.scalar(
        select(func.count(RosterOwnershipInterval.id)).where(
            RosterOwnershipInterval.league_id == UUID(league_id),
            RosterOwnershipInterval.athlete_id == athlete.id,
            RosterOwnershipInterval.released_at.is_(None),
        )
    )
    assert active == 1
