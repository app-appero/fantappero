"""Pro-tier league export: standings + audit trail size (EP11-05).

Read-only and additive — never touches competitive rules, credits, moves or
scores (EP11-05 acceptance). Cross-season "storico"/"albo d'oro" is out of
scope here: this MVP's data model is one season per league (see League/
LeagueRules), so there is no multi-season history to aggregate yet; this
export covers what the current single-season model actually has.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.pro_export_schemas import LeagueProExportResponse
from leagues.schemas import LeagueStandingResponse
from leagues.standings_service import list_league_standings
from fantasy_teams.models import FantasyTeam


def build_league_export(session: Session, *, league_id: UUID) -> LeagueProExportResponse:
    standings = list_league_standings(session, league_id=league_id)
    team_names = {
        team.id: team.name
        for team in session.scalars(
            select(FantasyTeam).where(FantasyTeam.league_id == league_id)
        ).all()
    }
    audit_count = (
        session.scalar(
            select(func.count())
            .select_from(LeagueAuditEvent)
            .where(LeagueAuditEvent.league_id == league_id)
        )
        or 0
    )
    return LeagueProExportResponse(
        leagueId=str(league_id),
        generatedAt=datetime.now(UTC),
        standings=[
            LeagueStandingResponse(
                fantasyTeamId=str(row.fantasy_team_id),
                teamName=team_names.get(row.fantasy_team_id, "Squadra"),
                position=row.position,
                played=row.played,
                won=row.won,
                drawn=row.drawn,
                lost=row.lost,
                fantasyGoalsFor=row.fantasy_goals_for,
                fantasyGoalsAgainst=row.fantasy_goals_against,
                fantasyPointsFor=row.fantasy_points_for,
                fantasyPointsAgainst=row.fantasy_points_against,
                points=row.points,
                computedAt=row.computed_at,
            )
            for row in standings
        ],
        auditEventsCount=audit_count,
    )
