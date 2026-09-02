"""Resolve the caller's own fantasy team within a league (shared by EP10-02/03)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from authorization.context import LeagueAccess
from fantasy_teams.factory import ensure_team_for_membership, find_team_for_membership
from fantasy_teams.models import FantasyTeam
from leagues.models.league_membership import LeagueMembership


def resolve_my_team(session: Session, league_access: LeagueAccess) -> FantasyTeam | None:
    membership = session.scalar(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league_access.league.id,
            LeagueMembership.user_id == league_access.user.id,
        )
    )
    if membership is None:
        return None
    ensure_team_for_membership(
        session,
        membership,
        name=league_access.user.display_name or "Squadra",
        actor_id=league_access.user.id,
    )
    return find_team_for_membership(session, membership.id)
