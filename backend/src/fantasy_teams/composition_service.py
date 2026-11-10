"""Resolve roster roles/competitions and sync composition status (EP05-05)."""

from __future__ import annotations

from dataclasses import dataclass
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
from sports_data.listone.generate import get_role_assignment, list_role_assignments
from sports_data.listone.mapping import map_provider_position_to_role
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.listone.overrides import effective_role_for_athlete, get_active_override
from sports_data.roster.models import SquadMembership


@dataclass(frozen=True)
class EffectiveAthleteRole:
    role: FantasyRole
    club_id: UUID | None


def resolve_effective_athlete_roles(
    session: Session,
    *,
    league_id: UUID,
    athlete_ids: list[UUID],
    season_year: int,
    current_round: int = 0,
    competition_ids: set[UUID] | None = None,
) -> dict[UUID, EffectiveAthleteRole]:
    """Resolve listone assignments and league overrides in two bulk queries."""
    unique_ids = list(dict.fromkeys(athlete_ids))
    if not unique_ids:
        return {}
    assignments = list_role_assignments(
        session,
        season_year=season_year,
        athlete_ids=unique_ids,
        competition_ids=competition_ids,
    )
    overrides = session.scalars(
        select(LeagueRoleOverride).where(
            LeagueRoleOverride.league_id == league_id,
            LeagueRoleOverride.athlete_id.in_(unique_ids),
            LeagueRoleOverride.superseded_at.is_(None),
        )
    ).all()
    overrides_by_athlete = {row.athlete_id: row for row in overrides}
    resolved = {
        assignment.athlete_id: EffectiveAthleteRole(
            role=effective_role_for_athlete(
                official_role=assignment.role,
                override=overrides_by_athlete.get(assignment.athlete_id),
                current_round=current_round,
            ),
            club_id=assignment.club_id,
        )
        for assignment in assignments
    }
    # Un calciatore in rosa senza ruolo per la stagione corrente (es. listone rigenerato senza di
    # lui) resterebbe senza ruolo in formazione e bloccherebbe il salvataggio: si ricade sull'ultimo
    # ruolo ufficiale noto, di qualsiasi stagione.
    missing = [athlete_id for athlete_id in unique_ids if athlete_id not in resolved]
    if missing:
        fallback_rows = session.scalars(
            select(RoleAssignment)
            .where(RoleAssignment.athlete_id.in_(missing))
            .order_by(RoleAssignment.season_year.desc())
        ).all()
        for row in fallback_rows:
            if row.athlete_id in resolved:
                continue
            resolved[row.athlete_id] = EffectiveAthleteRole(
                role=effective_role_for_athlete(
                    official_role=row.role,
                    override=overrides_by_athlete.get(row.athlete_id),
                    current_round=current_round,
                ),
                club_id=row.club_id,
            )
        missing = [athlete_id for athlete_id in missing if athlete_id not in resolved]
    if missing:
        # Calciatori entrati in rosa dopo l'ultima generazione del listone: hanno già la scheda
        # (posizione del provider) ma nessuna assegnazione di ruolo. Il ruolo si ricava dalla
        # posizione della loro appartenenza alla squadra in stagione (stesso mapping del listone).
        memberships = session.execute(
            select(SquadMembership)
            .join(SportSeason, SquadMembership.sport_season_id == SportSeason.id)
            .where(
                SquadMembership.athlete_id.in_(missing),
                SportSeason.year == season_year,
            )
            .order_by(SquadMembership.is_active.desc(), SquadMembership.updated_at.desc())
        ).scalars()
        for membership in memberships:
            if membership.athlete_id in resolved:
                continue
            role = map_provider_position_to_role(membership.provider_position_raw)
            if role is None:
                continue
            resolved[membership.athlete_id] = EffectiveAthleteRole(
                role=role,
                club_id=membership.club_id,
            )
    return resolved


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
    competition_ids: set[UUID] | None = None,
) -> FantasyRole | None:
    assignment = get_role_assignment(
        session,
        athlete_id=athlete_id,
        season_year=season_year,
        competition_ids=competition_ids,
    )
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
    effective_roles: dict[UUID, EffectiveAthleteRole] | None = None,
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

    athlete_ids = [slot.athlete_id for slot in slots if slot.athlete_id is not None]
    resolved = effective_roles
    if resolved is None:
        resolved = resolve_effective_athlete_roles(
            session,
            league_id=league.id,
            athlete_ids=athlete_ids,
            season_year=league.season_year,
        )
    roles = [resolved[athlete_id].role for athlete_id in athlete_ids if athlete_id in resolved]
    unresolved = len(athlete_ids) - len(roles)
    club_ids = {
        item.club_id
        for athlete_id, item in resolved.items()
        if athlete_id in athlete_ids and item.club_id is not None
    }

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
        competition_ids={competition.id for competition in league.competitions},
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


def assign_allowing_role_quota_overflow(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    athlete_id: UUID,
    slot_index: int,
) -> tuple[FantasyRole, bool]:
    """Like `assert_assignment_respects_role_quota`, but a quota overflow is allowed
    through instead of rejected — for trade acceptance only (EP08-10): the system
    revalidates everything else at acceptance time ("nessuna operazione parziale"),
    but a role already at its cap must not sink an otherwise-agreed trade. Returns
    `(role, exceeds_quota)`; the caller marks the slot so the player counts as
    owned but stays unavailable to field until released.
    """
    from auth.exceptions import ValidationAuthError

    try:
        role = assert_assignment_respects_role_quota(
            session,
            league=league,
            team=team,
            athlete_id=athlete_id,
            slot_index=slot_index,
        )
        return role, False
    except ValidationAuthError as exc:
        if exc.code != "role_quota_exceeded":
            raise
        role = resolve_effective_athlete_role(
            session,
            league_id=league.id,
            athlete_id=athlete_id,
            season_year=league.season_year,
            competition_ids={competition.id for competition in league.competitions},
        )
        if role is None:
            raise
        return role, True


def reconcile_role_quota_overflow(session: Session, *, league: League, team: FantasyTeam) -> None:
    """Clear `exceeds_role_quota` on any slot whose role is no longer actually over
    quota — called after anything that can change a team's roster composition
    (releasing a player, a trade). A role can stop being over quota either because
    the flagged player's own role was released, or because a *different* player of
    that same role left, freeing the limit for the one still flagged.
    """
    limits = resolve_league_rules_limits(session, league.id)
    slots = list(
        session.scalars(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == team.id,
                FantasyRosterSlot.athlete_id.isnot(None),
            )
        ).all()
    )
    if not slots:
        return
    athlete_ids = [slot.athlete_id for slot in slots if slot.athlete_id is not None]
    roles = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=athlete_ids,
        season_year=league.season_year,
        competition_ids={competition.id for competition in league.competitions},
    )
    role_counts: dict[FantasyRole, int] = {}
    flagged_by_role: dict[FantasyRole, list[FantasyRosterSlot]] = {}
    for slot in slots:
        resolved = roles.get(slot.athlete_id)
        if resolved is None:
            continue
        role_counts[resolved.role] = role_counts.get(resolved.role, 0) + 1
        if slot.exceeds_role_quota:
            flagged_by_role.setdefault(resolved.role, []).append(slot)
    for role, flagged_slots in flagged_by_role.items():
        over = max(0, role_counts.get(role, 0) - limits.for_role(role))
        # Keep exactly `over` flagged (still genuinely in excess); clear the rest —
        # the role count caught up with the quota for those, even if another
        # player of the same role is still queued behind them.
        for slot in flagged_slots[over:]:
            slot.exceeds_role_quota = False


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
                action_hint="teams",
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
                action_hint="teams",
            )
        )
    return blockers


def league_rosters_complete(session: Session, league: League) -> bool:
    """True se ogni membership ha una squadra con rosa completa e valida.

    Stesso controllo di composizione usato per sbloccare l'avvio stagione
    (`activation_roster_and_credit_blockers`), ma senza il vincolo sui
    crediti: qui serve solo sapere se le rose sono pronte per generare il
    calendario H2H (EP13-P04) — le rose si possono completare anche senza
    passare per lo stato "asta" (es. assegnazione manuale/random IA in
    Amministrazione lega), quindi il prerequisito è sulle rose stesse, non
    sullo stato macro della lega.
    """
    memberships = list(
        session.scalars(
            select(LeagueMembership).where(LeagueMembership.league_id == league.id)
        ).all()
    )
    if not memberships:
        return False
    teams = {
        team.membership_id: team
        for team in session.scalars(
            select(FantasyTeam).where(FantasyTeam.league_id == league.id)
        ).all()
    }
    for membership in memberships:
        team = teams.get(membership.id)
        if team is None:
            return False
        report = evaluate_team_composition(session, team, league=league, require_complete=True)
        if not report.is_valid_for_season_start:
            return False
    return True
