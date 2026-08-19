"""Integration tests for the Analista advisory service (EP10-04)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_assistant.analista_service import AnalistaService
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import LeagueMemberRole
from leagues.models.competition import Competition
from leagues.models.league import League
from mail.capture import get_captured_emails
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


def test_explanation_flags_low_sample_size_as_a_limit(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "analista-basic@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Analista"))
    league = db_session.get(League, league_id)
    user = db_session.get(User, user_id)

    athlete = Athlete(provider_id=960001, canonical_name="Giocatore Analizzato", injured=True)
    db_session.add(athlete)
    db_session.commit()

    league_access = LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)
    explanation = AnalistaService(db_session).explain(league_access, athlete.id)

    assert explanation is not None
    assert explanation.sample_size == 0
    assert "Campione ridotto" in explanation.limits
    assert "infortunato" in explanation.explanation
    assert explanation.cached is False


def test_second_call_within_ttl_is_served_from_cache(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "analista-cache@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Analista Cache"))
    league = db_session.get(League, league_id)
    user = db_session.get(User, user_id)

    athlete = Athlete(provider_id=960002, canonical_name="Giocatore Cache")
    db_session.add(athlete)
    db_session.commit()

    league_access = LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)
    service = AnalistaService(db_session)

    first = service.explain(league_access, athlete.id)
    second = service.explain(league_access, athlete.id)

    assert first is not None and second is not None
    assert first.cached is False
    assert second.cached is True
    assert second.interaction_id == first.interaction_id


def test_explanation_none_for_unknown_athlete(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "analista-unknown@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Analista Sconosciuto"))
    league = db_session.get(League, league_id)
    user = db_session.get(User, user_id)

    league_access = LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)
    assert AnalistaService(db_session).explain(league_access, UUID(int=0)) is None
