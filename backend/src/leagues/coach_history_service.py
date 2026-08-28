"""Storico fantallenatori letto dal database (EP13-P06).

Sola lettura. Espone solo fatti derivabili da leghe **concluse**: mai nomi di
lega, mai email, budget o rose. Un amministratore non deve poter dedurre a
quali leghe private altrui una persona partecipa.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.enums import LeagueState
from fantasy_teams.models import FantasyTeam
from leagues.coach_history import (
    CoachHistory,
    ConcludedPlacement,
    build_history,
)
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_standing import LeagueStanding

#: Una lega conta nello storico solo quando la stagione è chiusa.
CONCLUDED_STATES = (LeagueState.CONCLUDED, LeagueState.ARCHIVED)


def load_histories(session: Session, *, user_ids: list[UUID]) -> dict[UUID, CoachHistory]:
    """Storico di più utenti in **una sola query**, per evitare N+1 in lista."""
    if not user_ids:
        return {}

    participant_count = (
        select(func.count(LeagueStanding.id))
        .where(LeagueStanding.league_id == League.id)
        .correlate(League)
        .scalar_subquery()
    )

    rows = session.execute(
        select(
            LeagueMembership.user_id,
            League.season_year,
            LeagueStanding.position,
            LeagueStanding.played,
            LeagueStanding.points,
            LeagueStanding.fantasy_points_for,
            participant_count.label("participants"),
        )
        .join(FantasyTeam, FantasyTeam.membership_id == LeagueMembership.id)
        .join(LeagueStanding, LeagueStanding.fantasy_team_id == FantasyTeam.id)
        .join(League, League.id == LeagueMembership.league_id)
        .where(
            LeagueMembership.user_id.in_(user_ids),
            League.state.in_(CONCLUDED_STATES),
        )
    ).all()

    buckets: dict[UUID, list[ConcludedPlacement]] = {user_id: [] for user_id in user_ids}
    for user_id, season_year, position, played, points, fantasy_points, participants in rows:
        buckets.setdefault(user_id, []).append(
            ConcludedPlacement(
                season_year=season_year,
                position=position,
                participant_count=participants or 0,
                played=played,
                points=points,
                fantasy_points=fantasy_points,
            )
        )
    return {user_id: build_history(items) for user_id, items in buckets.items()}


def load_history(session: Session, *, user_id: UUID) -> CoachHistory:
    return load_histories(session, user_ids=[user_id]).get(user_id, build_history([]))


def utc_now() -> datetime:
    return datetime.now(UTC)
