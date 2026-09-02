"""Integration tests for the athlete feature store: no future leakage (EP10-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_assistant.feature_store import build_athlete_features
from database.enums import FantasyRole
from fantasy_ratings.models import PlayerMatchRating
from leagues.models.competition import Competition
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.roster.models import Athlete, SquadMembership


@pytest.fixture
def competition_id(db_session: Session) -> UUID:
    row = db_session.scalars(select(Competition).order_by(Competition.name.asc())).first()
    assert row is not None
    return row.id


def _season(db_session: Session, competition_id: UUID) -> SportSeason:
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id, SportSeason.year == 2026
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()
    return season


def _fixture(
    db_session: Session,
    season: SportSeason,
    home: Club,
    away: Club,
    *,
    provider_id: int,
    kickoff_at: datetime,
    status_short: str,
) -> Fixture:
    fixture = Fixture(
        provider_id=provider_id,
        sport_season_id=season.id,
        home_club_id=home.id,
        away_club_id=away.id,
        kickoff_at=kickoff_at,
        status_short=status_short,
    )
    db_session.add(fixture)
    db_session.flush()
    return fixture


def _rating(
    db_session: Session,
    fixture: Fixture,
    athlete: Athlete,
    *,
    display: float,
    minutes: int,
) -> None:
    db_session.add(
        PlayerMatchRating(
            fixture_id=fixture.id,
            athlete_id=athlete.id,
            athlete_provider_id=athlete.provider_id,
            formula_version="v1",
            role=FantasyRole.A,
            minutes=minutes,
            eligible=True,
            eligibility_reason="played",
            base=6.0,
            raw_before_clamp=display,
            raw=display,
            display=display,
            stats_hash=f"hash-{fixture.id}",
        )
    )


def test_features_exclude_ratings_from_fixtures_after_as_of(
    db_session: Session, competition_id: UUID
) -> None:
    season = _season(db_session, competition_id)
    home = Club(provider_id=910001, name="Club Feature Home")
    away = Club(provider_id=910002, name="Club Feature Away")
    opponent = Club(provider_id=910003, name="Club Feature Opponent")
    db_session.add_all([home, away, opponent])
    db_session.flush()

    athlete = Athlete(provider_id=920001, canonical_name="Bomber Feature", injured=False)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        SquadMembership(athlete_id=athlete.id, club_id=home.id, sport_season_id=season.id)
    )
    db_session.flush()

    as_of = datetime(2026, 3, 1, tzinfo=UTC)
    past_fixture = _fixture(
        db_session,
        season,
        home,
        away,
        provider_id=930001,
        kickoff_at=as_of - timedelta(days=7),
        status_short="FT",
    )
    _rating(db_session, past_fixture, athlete, display=8.0, minutes=90)

    future_fixture = _fixture(
        db_session,
        season,
        home,
        away,
        provider_id=930002,
        kickoff_at=as_of + timedelta(days=1),
        status_short="FT",
    )
    _rating(db_session, future_fixture, athlete, display=3.0, minutes=90)

    # Chronologically before future_fixture, so it is the true "next" match.
    next_opponent_fixture = _fixture(
        db_session,
        season,
        home,
        opponent,
        provider_id=930003,
        kickoff_at=as_of + timedelta(hours=6),
        status_short="NS",
    )
    db_session.commit()

    features = build_athlete_features(db_session, athlete.id, as_of=as_of)

    assert features is not None
    assert features.recent_ratings == (8.0,)
    assert features.avg_rating == 8.0
    assert features.recent_minutes_avg == 90.0
    assert features.next_opponent_name == "Club Feature Opponent"
    assert features.next_kickoff_at == next_opponent_fixture.kickoff_at
    assert features.injured is False


def test_features_report_free_agent_status_when_league_given(
    db_session: Session, competition_id: UUID
) -> None:
    athlete = Athlete(provider_id=920002, canonical_name="Svincolato Feature")
    db_session.add(athlete)
    db_session.commit()

    features = build_athlete_features(
        db_session,
        athlete.id,
        as_of=datetime.now(UTC),
        league_id=UUID(int=0),
    )

    assert features is not None
    assert features.is_free_agent_in_league is True


def test_features_none_for_unknown_athlete(db_session: Session) -> None:
    assert build_athlete_features(db_session, UUID(int=0), as_of=datetime.now(UTC)) is None
