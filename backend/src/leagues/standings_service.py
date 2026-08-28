"""Compute and persist league standings (EP07-06 / FR-CLS-01).

Always recomputed from the persisted H2H results (EP07-05), never
incremented: every call rebuilds the full table from ``league_calendar_slots``
where ``result_final`` is true and overwrites ``league_standings`` accordingly,
so a recalculation can never duplicate a match or a point (FR-CLS-01
criteri di accettazione).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from fantasy_teams.models import FantasyTeam
from leagues.models.league import League
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_standing import LeagueStanding
from leagues.standings import MatchResult, TeamRecord, build_standings, rank_standings

UpsertResult = str  # created | updated | unchanged


@dataclass
class StandingsCounters:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0

    def incr(self, result: UpsertResult) -> None:
        setattr(self, result, getattr(self, result) + 1)


@dataclass
class LeagueStandingsResult:
    league_id: UUID
    teams: int
    matches_considered: int
    counters: StandingsCounters = field(default_factory=StandingsCounters)


def compute_league_standings(session: Session, *, league_id: UUID) -> LeagueStandingsResult:
    league = session.get(League, league_id)
    if league is None:
        raise ValidationAuthError("Lega non trovata.", code="league_not_found")

    teams = list(
        session.scalars(select(FantasyTeam).where(FantasyTeam.league_id == league_id)).all()
    )
    team_ids = [team.id for team in teams]
    team_names = {team.id: team.name for team in teams}

    calendar = session.execute(
        select(LeagueCalendar).where(LeagueCalendar.league_id == league_id)
    ).scalar_one_or_none()

    matches: list[MatchResult] = []
    if calendar is not None:
        slots = list(
            session.scalars(
                select(LeagueCalendarSlot).where(
                    LeagueCalendarSlot.calendar_id == calendar.id,
                    LeagueCalendarSlot.is_bye.is_(False),
                    LeagueCalendarSlot.result_final.is_(True),
                    LeagueCalendarSlot.outcome.is_not(None),
                )
            ).all()
        )
        membership_ids = {slot.home_membership_id for slot in slots} | {
            slot.away_membership_id for slot in slots if slot.away_membership_id is not None
        }
        team_by_membership = _teams_by_membership(session, membership_ids)
        for slot in slots:
            home_team = team_by_membership.get(slot.home_membership_id)
            away_team = team_by_membership.get(slot.away_membership_id)
            if home_team is None or away_team is None:
                continue
            matches.append(
                MatchResult(
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    home_fantasy_goals=slot.home_fantasy_goals or 0,
                    away_fantasy_goals=slot.away_fantasy_goals or 0,
                    outcome=slot.outcome,
                    home_fantasy_points=slot.home_score,
                    away_fantasy_points=slot.away_score,
                )
            )

    records = build_standings(team_ids, matches)
    ranked = rank_standings(records, team_names=team_names)

    counters = StandingsCounters()
    computed_at = datetime.now(UTC)
    kept_ids: set[UUID] = set()
    for position, record in enumerate(ranked, start=1):
        row = _upsert_standing(
            session,
            league_id=league_id,
            record=record,
            position=position,
            computed_at=computed_at,
            counters=counters,
        )
        kept_ids.add(row.fantasy_team_id)

    stale_query = select(LeagueStanding).where(LeagueStanding.league_id == league_id)
    if kept_ids:
        stale_query = stale_query.where(LeagueStanding.fantasy_team_id.not_in(kept_ids))
    for row in session.scalars(stale_query).all():
        session.delete(row)
        counters.incr("removed")

    session.flush()
    return LeagueStandingsResult(
        league_id=league_id,
        teams=len(teams),
        matches_considered=len(matches),
        counters=counters,
    )


def list_league_standings(session: Session, *, league_id: UUID) -> list[LeagueStanding]:
    return list(
        session.scalars(
            select(LeagueStanding)
            .where(LeagueStanding.league_id == league_id)
            .order_by(LeagueStanding.position.asc())
        ).all()
    )


def _teams_by_membership(session: Session, membership_ids: set[UUID]) -> dict[UUID, FantasyTeam]:
    if not membership_ids:
        return {}
    memberships = session.scalars(
        select(LeagueMembership).where(LeagueMembership.id.in_(membership_ids))
    ).all()
    teams = session.scalars(
        select(FantasyTeam).where(FantasyTeam.membership_id.in_([m.id for m in memberships]))
    ).all()
    by_membership = {team.membership_id: team for team in teams}
    return {m.id: by_membership[m.id] for m in memberships if m.id in by_membership}


def _upsert_standing(
    session: Session,
    *,
    league_id: UUID,
    record: TeamRecord,
    position: int,
    computed_at: datetime,
    counters: StandingsCounters,
) -> LeagueStanding:
    row = session.execute(
        select(LeagueStanding).where(
            LeagueStanding.league_id == league_id,
            LeagueStanding.fantasy_team_id == record.fantasy_team_id,
        )
    ).scalar_one_or_none()

    if row is None:
        row = LeagueStanding(
            league_id=league_id,
            fantasy_team_id=record.fantasy_team_id,
            played=record.played,
            won=record.won,
            drawn=record.drawn,
            lost=record.lost,
            fantasy_goals_for=record.fantasy_goals_for,
            fantasy_goals_against=record.fantasy_goals_against,
            fantasy_points_for=record.fantasy_points_for,
            fantasy_points_against=record.fantasy_points_against,
            points=record.points,
            position=position,
            computed_at=computed_at,
        )
        session.add(row)
        counters.incr("created")
        return row

    unchanged = (
        row.played == record.played
        and row.won == record.won
        and row.drawn == record.drawn
        and row.lost == record.lost
        and row.fantasy_goals_for == record.fantasy_goals_for
        and row.fantasy_goals_against == record.fantasy_goals_against
        and row.fantasy_points_for == record.fantasy_points_for
        and row.fantasy_points_against == record.fantasy_points_against
        and row.points == record.points
        and row.position == position
    )
    if unchanged:
        counters.incr("unchanged")
        return row

    row.played = record.played
    row.won = record.won
    row.drawn = record.drawn
    row.lost = record.lost
    row.fantasy_goals_for = record.fantasy_goals_for
    row.fantasy_goals_against = record.fantasy_goals_against
    row.fantasy_points_for = record.fantasy_points_for
    row.fantasy_points_against = record.fantasy_points_against
    row.points = record.points
    row.position = position
    row.computed_at = computed_at
    counters.incr("updated")
    return row
