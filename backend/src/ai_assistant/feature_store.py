"""Athlete feature store for AI-assisted advice (EP10-01).

Every feature is computed strictly relative to an ``as_of`` timestamp: past
form/minutes are read from fixtures with ``kickoff_at < as_of`` and the next
opponent is the first fixture with ``kickoff_at >= as_of``. This is the only
guard against leakage — callers must always pass a real "now", never a value
derived from data the advice is meant to be about.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRole
from fantasy_ratings.models import PlayerMatchRating
from fantasy_teams.models import FantasyRosterSlot
from sports_data.catalog.models import Club
from sports_data.fixtures.models import Fixture
from sports_data.roster.models import Athlete, SquadMembership

DEFAULT_LOOKBACK = 5


@dataclass(frozen=True)
class AthleteFeatures:
    athlete_id: UUID
    canonical_name: str
    role: FantasyRole | None
    as_of: datetime
    injured: bool | None
    recent_ratings: tuple[float, ...]
    avg_rating: float | None
    recent_minutes_avg: float | None
    club_name: str | None
    next_opponent_name: str | None
    next_kickoff_at: datetime | None
    is_free_agent_in_league: bool | None


def _current_club(session: Session, athlete_id: UUID) -> tuple[UUID, str] | None:
    row = session.execute(
        select(SquadMembership.club_id)
        .where(SquadMembership.athlete_id == athlete_id)
        .order_by(SquadMembership.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    club = session.get(Club, row[0])
    if club is None:
        return None
    return club.id, club.name


def _next_fixture(session: Session, club_id: UUID, *, as_of: datetime) -> Fixture | None:
    return session.scalar(
        select(Fixture)
        .where(
            Fixture.kickoff_at.is_not(None),
            Fixture.kickoff_at >= as_of,
            (Fixture.home_club_id == club_id) | (Fixture.away_club_id == club_id),
        )
        .order_by(Fixture.kickoff_at.asc())
        .limit(1)
    )


def build_athlete_features(
    session: Session,
    athlete_id: UUID,
    *,
    as_of: datetime,
    league_id: UUID | None = None,
    lookback: int = DEFAULT_LOOKBACK,
) -> AthleteFeatures | None:
    athlete = session.get(Athlete, athlete_id)
    if athlete is None:
        return None

    rows = session.execute(
        select(PlayerMatchRating.display, PlayerMatchRating.raw, PlayerMatchRating.minutes)
        .join(Fixture, Fixture.id == PlayerMatchRating.fixture_id)
        .where(
            PlayerMatchRating.athlete_id == athlete_id,
            PlayerMatchRating.eligible.is_(True),
            Fixture.kickoff_at.is_not(None),
            Fixture.kickoff_at < as_of,
        )
        .order_by(Fixture.kickoff_at.desc())
        .limit(lookback)
    ).all()
    ratings = tuple(
        float(display if display is not None else raw) for display, raw, _minutes in rows
    )
    minutes_values = [minutes for _display, _raw, minutes in rows if minutes is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
    avg_minutes = round(sum(minutes_values) / len(minutes_values), 1) if minutes_values else None

    club = _current_club(session, athlete_id)
    club_name = club[1] if club else None
    next_fixture = _next_fixture(session, club[0], as_of=as_of) if club else None
    next_opponent_name = None
    if next_fixture is not None and club is not None:
        opponent_id = (
            next_fixture.away_club_id
            if next_fixture.home_club_id == club[0]
            else next_fixture.home_club_id
        )
        opponent = session.get(Club, opponent_id)
        next_opponent_name = opponent.name if opponent else None

    is_free_agent: bool | None = None
    if league_id is not None:
        occupied = session.scalar(
            select(FantasyRosterSlot.id).where(
                FantasyRosterSlot.league_id == league_id,
                FantasyRosterSlot.athlete_id == athlete_id,
            )
        )
        is_free_agent = occupied is None

    role_row = session.execute(
        select(PlayerMatchRating.role)
        .where(PlayerMatchRating.athlete_id == athlete_id, PlayerMatchRating.role.is_not(None))
        .order_by(PlayerMatchRating.created_at.desc())
        .limit(1)
    ).first()

    return AthleteFeatures(
        athlete_id=athlete_id,
        canonical_name=athlete.canonical_name,
        role=role_row[0] if role_row else None,
        as_of=as_of,
        injured=athlete.injured,
        recent_ratings=ratings,
        avg_rating=avg_rating,
        recent_minutes_avg=avg_minutes,
        club_name=club_name,
        next_opponent_name=next_opponent_name,
        next_kickoff_at=next_fixture.kickoff_at if next_fixture else None,
        is_free_agent_in_league=is_free_agent,
    )
