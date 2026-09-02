"""Integration tests for live score/homologation fields on turn detail (EP09-04)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyTurnKind, FantasyTurnStatus
from database.session import create_session_factory
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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


def test_turn_detail_exposes_live_score_and_homologation_status(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, _ = _register_and_login(client, "live-fields@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Live")

    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(days=1),
        window_end_at=now + timedelta(days=1),
        cutoff_at=now - timedelta(minutes=30),
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now - timedelta(days=1),
    )
    db_session.add(fantasy_round)
    db_session.flush()

    home = Club(provider_id=960001, name="Club Live A")
    away = Club(provider_id=960002, name="Club Live B")
    db_session.add_all([home, away])
    db_session.flush()

    competition_id = UUID(competition_ids[0])
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id, SportSeason.year == 2026
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()

    fixture = Fixture(
        provider_id=960050,
        sport_season_id=season.id,
        home_club_id=home.id,
        away_club_id=away.id,
        kickoff_at=now - timedelta(minutes=30),
        status_short="2H",
        status_elapsed=63,
        home_goals=1,
        away_goals=2,
    )
    db_session.add(fixture)
    db_session.flush()
    db_session.add(
        FantasyRoundFixture(
            round_id=fantasy_round.id,
            league_id=UUID(league_id),
            fixture_id=fixture.id,
            observed_kickoff_at=fixture.kickoff_at,
        )
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["homologationStatus"] == "provisional"
    fixture_body = body["fixtures"][0]
    assert fixture_body["statusShort"] == "2H"
    assert fixture_body["statusElapsed"] == 63
    assert fixture_body["homeGoals"] == 1
    assert fixture_body["awayGoals"] == 2
