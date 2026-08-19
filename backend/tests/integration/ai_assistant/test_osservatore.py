"""Integration tests for the Osservatore advisory service (EP10-03)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_assistant.osservatore_service import OsservatoreService
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import FantasyRole, LeagueMemberRole
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.competition import Competition
from leagues.models.league import League
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
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


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


def test_compare_returns_a_row_per_known_athlete(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "osserv-compare@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Osservatore"))
    league = db_session.get(League, league_id)
    user = db_session.get(User, user_id)

    one = Athlete(provider_id=950001, canonical_name="Confronto Uno")
    two = Athlete(provider_id=950002, canonical_name="Confronto Due")
    db_session.add_all([one, two])
    db_session.commit()

    league_access = LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)
    result = OsservatoreService(db_session).compare(league_access, [one.id, two.id])

    names = {row.name for row in result.rows}
    assert names == {"Confronto Uno", "Confronto Due"}
    assert result.interaction_id is not None


def test_free_agent_targets_exclude_occupied_and_filter_by_role(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "osserv-targets@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Osservatore Target"))
    league = db_session.get(League, league_id)
    user = db_session.get(User, user_id)
    team = db_session.scalars(select(FantasyTeam).where(FantasyTeam.league_id == league_id)).one()

    free_agent = Athlete(provider_id=950003, canonical_name="Svincolato Libero")
    occupied = Athlete(provider_id=950004, canonical_name="Svincolato Occupato")
    wrong_role = Athlete(provider_id=950005, canonical_name="Ruolo Sbagliato")
    db_session.add_all([free_agent, occupied, wrong_role])
    db_session.flush()

    db_session.add_all(
        [
            RoleAssignment(
                athlete_id=free_agent.id, season_year=2026, role=FantasyRole.A, mapping_version="v1"
            ),
            RoleAssignment(
                athlete_id=occupied.id, season_year=2026, role=FantasyRole.A, mapping_version="v1"
            ),
            RoleAssignment(
                athlete_id=wrong_role.id, season_year=2026, role=FantasyRole.D, mapping_version="v1"
            ),
        ]
    )
    db_session.flush()

    slot = db_session.scalars(
        select(FantasyRosterSlot)
        .where(FantasyRosterSlot.fantasy_team_id == team.id, FantasyRosterSlot.athlete_id.is_(None))
        .limit(1)
    ).one()
    slot.athlete_id = occupied.id
    db_session.commit()

    league_access = LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)
    result = OsservatoreService(db_session).suggest_free_agent_targets(
        league_access, role=FantasyRole.A, season_year=2026, limit=10
    )

    names = {row.name for row in result.rows}
    assert names == {"Svincolato Libero"}
