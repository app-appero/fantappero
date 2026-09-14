"""Auto-conclusione stagione quando tutte le giornate H2H sono omologate."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import (
    FantasyRoundHomologationStatus,
    LeagueAuditAction,
    LeagueCalendarStatus,
    LeagueMemberRole,
    LeagueState,
)
from leagues.calendar_round_mapping import rounds_by_h2h_number
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


def try_conclude_league_if_season_complete(
    session: Session,
    league_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> bool:
    """Se la lega è ACTIVE e ogni giornata H2H ha il turno omologato → CONCLUDED.

    Ritorna True se lo stato è stato aggiornato. Idempotente: se non è ancora
    il momento (o la lega non è attiva) non fa nulla.
    """
    league = session.get(League, league_id)
    if league is None or league.state != LeagueState.ACTIVE:
        return False

    calendar = session.scalars(
        select(LeagueCalendar).where(
            LeagueCalendar.league_id == league_id,
            LeagueCalendar.status == LeagueCalendarStatus.CONFIRMED,
        )
    ).first()
    if calendar is None:
        return False

    h2h_numbers = set(
        session.scalars(
            select(LeagueCalendarSlot.round_number)
            .where(LeagueCalendarSlot.calendar_id == calendar.id)
            .distinct()
        ).all()
    )
    if not h2h_numbers:
        return False

    mapped = rounds_by_h2h_number(session, league_id=league_id, calendar=calendar)
    for number in h2h_numbers:
        fantasy_round = mapped.get(number)
        if fantasy_round is None:
            return False
        if fantasy_round.homologation_status != FantasyRoundHomologationStatus.HOMOLOGATED:
            return False

    audit_actor_id = actor_id
    if audit_actor_id is None:
        owner = session.scalars(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.role == LeagueMemberRole.OWNER,
            )
        ).first()
        audit_actor_id = owner.user_id if owner is not None else None

    league.state = LeagueState.CONCLUDED
    session.add(
        LeagueAuditEvent(
            league_id=league_id,
            actor_id=audit_actor_id,
            action=LeagueAuditAction.LEAGUE_STATE_CHANGED,
            correlation_id=get_correlation_id(),
            details={
                "before": LeagueState.ACTIVE.value,
                "after": LeagueState.CONCLUDED.value,
                "source": "auto_season_complete",
            },
        )
    )
    get_metrics().incr(
        "league_state_transition_total",
        labels={"result": "success", "from": "active", "to": "concluded"},
    )
    logger.info(
        "league_state_transition",
        extra={
            "result": "success",
            "from": "active",
            "to": "concluded",
            "source": "auto_season_complete",
            "league_id": str(league_id),
        },
    )
    return True
