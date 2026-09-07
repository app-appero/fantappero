"""Integration tests for random AI roster assignment."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.security import hash_password
from database.enums import FantasyRole, LeagueMemberRole, PlatformRole, UserType
from database.session import create_session_factory
from fantasy_teams.models import FantasyRosterSlot
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
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


def _seed_athlete(
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole,
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


def _seed_role_pool(db_session: Session, *, start_provider_id: int = 900_000) -> None:
    quotas = (
        (FantasyRole.P, 3),
        (FantasyRole.D, 11),
        (FantasyRole.C, 11),
        (FantasyRole.A, 10),
    )
    provider_id = start_provider_id
    for role, count in quotas:
        for index in range(count):
            _seed_athlete(
                db_session,
                provider_id,
                f"Random {role.value} {index + 1}",
                role=role,
            )
            provider_id += 1


def _seed_athlete_outside_competitions(
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole,
    season_year: int = 2026,
) -> Athlete:
    """An athlete whose only club plays in a competition the league never joined —
    a candidate the random-fill pool must exclude (EP05-08 regression)."""
    other_competition = Competition(
        provider_id=990100 + provider_id, name=f"Campionato Escluso {provider_id}", country="XX"
    )
    db_session.add(other_competition)
    db_session.flush()
    club = Club(provider_id=provider_id, name=f"Club Escluso {provider_id}")
    db_session.add(club)
    db_session.flush()
    season = SportSeason(competition_id=other_competition.id, year=season_year)
    db_session.add(season)
    db_session.flush()
    db_session.add(CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id))
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
            club_id=club.id,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _create_ai_member(
    db_session: Session, league_id: str, *, email: str = "ai.random.roster@ai-managers.example.com"
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("unused-secret"),
        platform_role=PlatformRole.USER,
        user_type=UserType.AI,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id,
            display_name="Allenatore IA Random",
            available_for_invites=True,
        )
    )
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=user.id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()
    db_session.refresh(user)
    return user


def test_assign_random_ai_roster_fills_complete_composition(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "random.ai.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Random IA")
    ai_user = _create_ai_member(db_session, league_id)
    _seed_role_pool(db_session)

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ensured.status_code == 200
    teams = ensured.json()["teams"]
    ai_team = next(team for team in teams if team["userId"] == str(ai_user.id))
    assert ai_team["userType"] == "ai"
    assert ai_team["filledSlots"] == 0

    response = client.post(
        f"/leagues/{league_id}/amministrazione/squadre/{ai_team['id']}/rosa/random",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["userType"] == "ai"
    assert body["filledSlots"] == 35
    assert body["composition"]["counts"] == {"P": 3, "D": 11, "C": 11, "A": 10}

    filled = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(ai_team["id"]),
            FantasyRosterSlot.athlete_id.is_not(None),
        )
    )
    assert filled is not None

    members = client.get(
        f"/leagues/{league_id}/amministrazione/partecipanti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert members.status_code == 200
    ai_member = next(row for row in members.json() if row["userId"] == str(ai_user.id))
    assert ai_member["userType"] == "ai"


def test_assign_random_ai_roster_ignores_athletes_outside_league_competitions(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """A league scoped to a subset of competitions must never have the random
    fill pick an athlete whose only role assignment sits in a competition it
    never joined — that used to slip into the candidate pool and blow up
    later as "role_unresolved" (EP05-08 regression)."""
    token, _ = _register_and_login(client, "random.ai.scoped@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Random IA Scoped")
    ai_user = _create_ai_member(
        db_session, league_id, email="ai.random.roster.scoped@ai-managers.example.com"
    )
    _seed_role_pool(db_session, start_provider_id=920_000)

    decoy_ids = {
        str(
            _seed_athlete_outside_competitions(
                db_session, 930_000 + index, f"Decoy {role.value} {index}", role=role
            ).id
        )
        for index, role in enumerate([FantasyRole.A] * 5 + [FantasyRole.D] * 5)
    }

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ensured.status_code == 200
    ai_team = next(
        team for team in ensured.json()["teams"] if team["userId"] == str(ai_user.id)
    )

    response = client.post(
        f"/leagues/{league_id}/amministrazione/squadre/{ai_team['id']}/rosa/random",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["filledSlots"] == 35
    assert body["composition"]["counts"] == {"P": 3, "D": 11, "C": 11, "A": 10}

    assigned_ids = {
        str(slot["athleteId"])
        for slot in body["slots"]
        if slot["athleteId"] is not None
    }
    assert assigned_ids.isdisjoint(decoy_ids)


def test_assign_random_ai_roster_rejects_human_team(
    client: TestClient,
    competition_ids: list[str],
    db_session: Session,
) -> None:
    token, owner_id = _register_and_login(client, "random.human.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Human Random")
    _seed_role_pool(db_session, start_provider_id=910_000)

    teams = client.get(
        f"/leagues/{league_id}/squadre",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert teams.status_code == 200
    owner_team = next(team for team in teams.json() if team["userId"] == str(owner_id))
    assert owner_team["userType"] == "human"

    response = client.post(
        f"/leagues/{league_id}/amministrazione/squadre/{owner_team['id']}/rosa/random",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "not_ai_manager"
