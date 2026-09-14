"""Auto-avanzamento lifecycle: draft→configuring, setup→active quando pronto."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from database.enums import LeagueAuditAction, LeagueMemberRole, LeagueState
from fantasy_teams.composition_service import activation_roster_and_credit_blockers
from leagues.calendar_service import league_has_confirmed_calendar
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.validators import (
    MAX_PARTICIPANTS,
    MIN_PARTICIPANTS,
    STANDARD_DEFENDERS,
    STANDARD_FORWARDS,
    STANDARD_GOALKEEPERS,
    STANDARD_MIDFIELDERS,
    STANDARD_PRESET_NAME,
    STANDARD_ROSTER_SIZE,
    auction_activation_blockers,
    configuration_blockers,
)
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


def try_advance_league_lifecycle(
    session: Session,
    league_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> LeagueState | None:
    """Avanza lo stato lega senza CTA manuali.

    - ``draft`` → ``configuring`` (sempre)
    - ``configuring`` / ``auction`` → ``active`` quando i blocker di avvio
      stagione sono vuoti (partecipanti, calendario confermato, rose/crediti)

    Idempotente. Ritorna lo stato raggiunto se ha cambiato qualcosa, altrimenti
    ``None``. Non fa ``commit``: il chiamante decide il flush/commit.
    """
    league = session.scalars(
        select(League)
        .where(League.id == league_id)
        .options(selectinload(League.competitions), selectinload(League.rules))
        .with_for_update()
    ).first()
    if league is None:
        return None

    audit_actor_id = actor_id
    if audit_actor_id is None:
        owner = session.scalars(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.role == LeagueMemberRole.OWNER,
            )
        ).first()
        audit_actor_id = owner.user_id if owner is not None else None

    changed_to: LeagueState | None = None

    if league.state == LeagueState.DRAFT:
        _apply_state_change(
            session,
            league,
            before=LeagueState.DRAFT,
            after=LeagueState.CONFIGURING,
            actor_id=audit_actor_id,
            source="auto_setup",
        )
        changed_to = LeagueState.CONFIGURING

    if league.state in (LeagueState.CONFIGURING, LeagueState.AUCTION):
        if _activation_blockers(session, league):
            return changed_to
        before = league.state
        _apply_state_change(
            session,
            league,
            before=before,
            after=LeagueState.ACTIVE,
            actor_id=audit_actor_id,
            source="auto_season_start",
        )
        return LeagueState.ACTIVE

    return changed_to


def _activation_blockers(session: Session, league: League) -> list[object]:
    rules = league.rules
    membership_count = session.scalar(
        select(func.count(LeagueMembership.id)).where(LeagueMembership.league_id == league.id)
    )
    owner_count = session.scalar(
        select(func.count(LeagueMembership.id)).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.role == LeagueMemberRole.OWNER,
        )
    )
    blockers = list(
        configuration_blockers(
            rules_valid=_rules_are_valid(rules),
            competition_count=len(league.competitions),
            membership_count=membership_count or 0,
            participant_count=rules.participant_count if rules is not None else None,
            owner_count=owner_count or 0,
        )
    )
    blockers.extend(
        auction_activation_blockers(
            calendar_configured=league_has_confirmed_calendar(session, league.id),
            roster_blockers=activation_roster_and_credit_blockers(session, league),
        )
    )
    return blockers


def _rules_are_valid(rules: LeagueRules | None) -> bool:
    return bool(
        rules is not None
        and rules.preset_name == STANDARD_PRESET_NAME
        and MIN_PARTICIPANTS <= rules.participant_count <= MAX_PARTICIPANTS
        and rules.roster_size == STANDARD_ROSTER_SIZE
        and rules.goalkeepers == STANDARD_GOALKEEPERS
        and rules.defenders == STANDARD_DEFENDERS
        and rules.midfielders == STANDARD_MIDFIELDERS
        and rules.forwards == STANDARD_FORWARDS
        and rules.goalkeepers + rules.defenders + rules.midfielders + rules.forwards
        == rules.roster_size
        and rules.total_credits > 0
    )


def _apply_state_change(
    session: Session,
    league: League,
    *,
    before: LeagueState,
    after: LeagueState,
    actor_id: UUID | None,
    source: str,
) -> None:
    league.state = after
    session.add(
        LeagueAuditEvent(
            league_id=league.id,
            actor_id=actor_id,
            action=LeagueAuditAction.LEAGUE_STATE_CHANGED,
            correlation_id=get_correlation_id(),
            details={
                "before": before.value,
                "after": after.value,
                "source": source,
            },
        )
    )
    get_metrics().incr(
        "league_state_transition_total",
        labels={"result": "success", "from": before.value, "to": after.value},
    )
    logger.info(
        "league_state_transition",
        extra={
            "result": "success",
            "from": before.value,
            "to": after.value,
            "source": source,
            "league_id": str(league.id),
        },
    )
