"""Resolve roster roles/competitions and sync composition status (EP05-05)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRole, LeagueState, RosterCompositionStatus
from fantasy_teams.composition import (
    RosterCompositionLimits,
    RosterCompositionReport,
    evaluate_roster_composition,
    limits_from_rules,
    would_exceed_role_quota,
)
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league import League
from leagues.models.league_competition import LeagueCompetition
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.validators import LifecycleBlocker
from sports_data.catalog.models import CompetitionSeasonClub, SportSeason
from sports_data.listone.generate import get_role_assignment
from sports_data.listone.overrides import effective_role_for_athlete, get_active_override


def resolve_league_rules_limits(session: Session, league_id: UUID) -> RosterCompositionLimits:
    rules = session.scalar(select(LeagueRules).where(LeagueRules.league_id == league_id))
    if rules is None:
        return limits_from_rules(
            roster_size=35,
            goalkeepers=3,
            defenders=11,
            midfielders=11,
            forwards=10,
        )
    return limits_from_rules(
        roster_size=rules.roster_size,
        goalkeepers=rules.goalkeepers,
        defenders=rules.defenders,
        midfielders=rules.midfielders,
        forwards=rules.forwards,
    )


def league_requires_complete_rosters(league: League) -> bool:
    """Incomplete rosters are allowed only before season start (during auction)."""
    return league.state not in {LeagueState.DRAFT, LeagueState.CONFIGURING, LeagueState.AUCTION}


def resolve_effective_athlete_role(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
    season_year: int,
    current_round: int = 0,
) -> FantasyRole | None:
    assignment = get_role_assignment(session, athlete_id=athlete_id, season_year=season_year)
    if assignment is None:
        return None
    override = get_active_override(session, league_id=league_id, athlete_id=athlete_id)
    return effective_role_for_athlete(
        official_role=assignment.role,
        override=override,
        current_round=current_round,
    )


def resolve_club_competition_ids(
    session: Session,
    *,
    club_ids: set[UUID],
    season_year: int,
    league_competition_ids: set[UUID],
) -> dict[UUID, set[UUID]]:
    """Map club → competition ids intersecting the league catalog for the season year."""
    if not club_ids or not league_competition_ids:
        return {}
    rows = session.execute(
        select(CompetitionSeasonClub.club_id, SportSeason.competition_id)
        .join(SportSeason, SportSeason.id == CompetitionSeasonClub.sport_season_id)
        .where(
            CompetitionSeasonClub.club_id.in_(club_ids),
            SportSeason.year == season_year,
            SportSeason.competition_id.in_(league_competition_ids),
        )
    ).all()
    mapping: dict[UUID, set[UUID]] = {}
    for club_id, competition_id in rows:
        mapping.setdefault(club_id, set()).add(competition_id)
    return mapping


def evaluate_team_composition(
    session: Session,
    team: FantasyTeam,
    *,
    league: League,
    require_complete: bool | None = None,
) -> RosterCompositionReport:
    limits = resolve_league_rules_limits(session, league.id)
    must_complete = (
        league_requires_complete_rosters(league) if require_complete is None else require_complete
    )
    league_competition_ids = {
        row.competition_id
        for row in session.scalars(
            select(LeagueCompetition).where(LeagueCompetition.league_id == league.id)
        ).all()
    }

    slots = list(
        session.scalars(
            select(FantasyRosterSlot)
            .where(FantasyRosterSlot.fantasy_team_id == team.id)
            .order_by(FantasyRosterSlot.slot_index.asc())
        ).all()
    )

    roles: list[FantasyRole | None] = []
    unresolved = 0
    club_ids: set[UUID] = set()
    for slot in slots:
        if slot.athlete_id is None:
            continue
        assignment = get_role_assignment(
            session,
            athlete_id=slot.athlete_id,
            season_year=league.season_year,
        )
        if assignment is None:
            unresolved += 1
            continue
        override = get_active_override(
            session,
            league_id=league.id,
            athlete_id=slot.athlete_id,
        )
        role = effective_role_for_athlete(
            official_role=assignment.role,
            override=override,
            current_round=0,
        )
        roles.append(role)
        if assignment.club_id is not None:
            club_ids.add(assignment.club_id)

    club_competitions = resolve_club_competition_ids(
        session,
        club_ids=club_ids,
        season_year=league.season_year,
        league_competition_ids=league_competition_ids,
    )
    competition_ids: set[UUID] = set()
    for comps in club_competitions.values():
        competition_ids.update(comps)

    return evaluate_roster_composition(
        limits=limits,
        roles=roles,
        competition_ids=competition_ids,
        require_complete=must_complete,
        unresolved_role_count=unresolved,
    )


def sync_team_composition_status(
    session: Session,
    team: FantasyTeam,
    *,
    league: League,
    require_complete: bool | None = None,
) -> RosterCompositionReport:
    report = evaluate_team_composition(
        session,
        team,
        league=league,
        require_complete=require_complete,
    )
    previous = team.composition_status
    team.composition_status = report.status
    if report.status == RosterCompositionStatus.VALIDATED:
        if team.validated_at is None or previous != RosterCompositionStatus.VALIDATED:
            team.validated_at = datetime.now(UTC)
    else:
        team.validated_at = None
    return report


def assert_assignment_respects_role_quota(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    athlete_id: UUID,
    slot_index: int,
) -> FantasyRole:
    """Reject assignments that would exceed configurable role limits."""
    from auth.exceptions import ValidationAuthError
    from fantasy_teams.composition import ROLE_LABEL_IT

    limits = resolve_league_rules_limits(session, league.id)
    new_role = resolve_effective_athlete_role(
        session,
        league_id=league.id,
        athlete_id=athlete_id,
        season_year=league.season_year,
    )
    if new_role is None:
        raise ValidationAuthError(
            "Il calciatore non ha un ruolo listone valido (P–D–C–A).",
            code="role_unresolved",
        )

    slots = list(
        session.scalars(
            select(FantasyRosterSlot).where(FantasyRosterSlot.fantasy_team_id == team.id)
        ).all()
    )
    current_roles: list[FantasyRole | None] = []
    replacing: FantasyRole | None = None
    for slot in slots:
        if slot.athlete_id is None:
            continue
        role = resolve_effective_athlete_role(
            session,
            league_id=league.id,
            athlete_id=slot.athlete_id,
            season_year=league.season_year,
        )
        if slot.slot_index == slot_index:
            replacing = role
            continue
        current_roles.append(role)

    if would_exceed_role_quota(
        limits=limits,
        current_roles=current_roles,
        new_role=new_role,
        replacing_role=replacing,
    ):
        limit = limits.for_role(new_role)
        raise ValidationAuthError(
            f"Limite {ROLE_LABEL_IT[new_role]} raggiunto ({limit}).",
            code="role_quota_exceeded",
        )
    return new_role


def activation_roster_and_credit_blockers(
    session: Session,
    league: League,
) -> list[LifecycleBlocker]:
    """Real season-start blockers replacing EP03-05 placeholders (EP05-05)."""
    from sqlalchemy.orm import selectinload

    from fantasy_teams.ledger import find_account_for_team

    blockers: list[LifecycleBlocker] = []
    memberships = list(
        session.scalars(
            select(LeagueMembership).where(LeagueMembership.league_id == league.id)
        ).all()
    )
    teams = {
        team.membership_id: team
        for team in session.scalars(
            select(FantasyTeam)
            .where(FantasyTeam.league_id == league.id)
            .options(
                selectinload(FantasyTeam.slots),
                selectinload(FantasyTeam.credit_account),
            )
        ).all()
    }

    missing_teams = 0
    invalid_rosters = 0
    missing_credits = 0
    for membership in memberships:
        team = teams.get(membership.id)
        if team is None:
            missing_teams += 1
            continue
        report = evaluate_team_composition(
            session,
            team,
            league=league,
            require_complete=True,
        )
        if not report.is_valid_for_season_start:
            invalid_rosters += 1
        account = team.credit_account or find_account_for_team(session, team.id)
        if account is None or account.balance < 0:
            missing_credits += 1

    if missing_teams or invalid_rosters:
        detail_parts: list[str] = []
        if missing_teams:
            detail_parts.append(f"{missing_teams} squadre mancanti")
        if invalid_rosters:
            detail_parts.append(f"{invalid_rosters} rose non valide o incomplete")
        blockers.append(
            LifecycleBlocker(
                code="fantasy_teams_not_configured",
                message=(
                    "Completa squadre e rose prima di avviare la stagione "
                    f"({'; '.join(detail_parts)})."
                ),
            )
        )
    if missing_credits:
        blockers.append(
            LifecycleBlocker(
                code="credits_not_configured",
                message=(
                    "Verifica i crediti di tutte le squadre prima di avviare la stagione "
                    f"({missing_credits} conti assenti o non validi)."
                ),
            )
        )
    return blockers
