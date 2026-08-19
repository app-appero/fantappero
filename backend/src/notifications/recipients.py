"""Fantasy-team → user_id lookups shared by notification producers (EP09-02/03)."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fantasy_teams.models import FantasyTeam
from leagues.models.league_membership import LeagueMembership


def user_ids_for_teams(session: Session, team_ids: Iterable[UUID]) -> dict[UUID, UUID]:
    """Map ``fantasy_team_id -> user_id`` for the given teams."""
    ids = list({team_id for team_id in team_ids})
    if not ids:
        return {}
    rows = session.execute(
        select(FantasyTeam.id, LeagueMembership.user_id)
        .join(LeagueMembership, FantasyTeam.membership_id == LeagueMembership.id)
        .where(FantasyTeam.id.in_(ids))
    ).all()
    return dict(rows)


def user_ids_for_league(session: Session, league_id: UUID) -> list[tuple[UUID, UUID]]:
    """``(fantasy_team_id, user_id)`` pairs for every team in a league."""
    return list(
        session.execute(
            select(FantasyTeam.id, LeagueMembership.user_id)
            .join(LeagueMembership, FantasyTeam.membership_id == LeagueMembership.id)
            .where(FantasyTeam.league_id == league_id)
        ).all()
    )
