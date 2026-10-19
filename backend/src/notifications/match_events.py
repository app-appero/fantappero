"""Notifiche live per gol, espulsioni e indisponibilità (EP09-05).

Avvisa solo chi ha il giocatore in rosa (non tutta la lega, sarebbe spam).
Mai bloccante: un errore qui non deve far fallire la sincronizzazione dei
dati partita, che è il lavoro vero. Riusa la categoria ``risultati``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import NotificationCategory
from fantasy_teams.models import FantasyRosterSlot
from notifications.recipients import user_ids_for_teams
from notifications.service import NotificationService
from observability.logging import get_logger
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

LIVE_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"})
_GOAL_KINDS = frozenset({"goal", "penalty_scored"})


def _owner_user_ids(session: Session, athlete_id: UUID) -> set[UUID]:
    team_ids = session.scalars(
        select(FantasyRosterSlot.fantasy_team_id).where(FantasyRosterSlot.athlete_id == athlete_id)
    ).all()
    return set(user_ids_for_teams(session, team_ids).values())


def _notify_owners(
    session: Session,
    *,
    athlete_id: UUID,
    template_key: str,
    params: dict[str, object],
    dedup_prefix: str,
) -> int:
    athlete = session.get(Athlete, athlete_id)
    if athlete is None:
        return 0
    params = {**params, "player": athlete.canonical_name}
    service = NotificationService(session)
    sent = 0
    for user_id in _owner_user_ids(session, athlete_id):
        with session.begin_nested():
            _, created = service.create_notification(
                user_id=user_id,
                category=NotificationCategory.RISULTATI,
                template_key=template_key,
                template_version=1,
                params=params,
                dedup_key=f"{dedup_prefix}:{user_id}",
            )
        sent += 1 if created else 0
    return sent


def notify_match_event(session: Session, *, event: object, fixture_status: str | None) -> int:
    """Chiamata alla creazione di un ``MatchEvent``. Ritorna le notifiche create."""
    athlete_id = getattr(event, "athlete_id", None)
    if athlete_id is None or fixture_status not in LIVE_STATUSES:
        return 0
    scoring_kind = getattr(event, "scoring_kind", None)
    event_type = (getattr(event, "event_type", "") or "").lower()
    detail = (getattr(event, "event_detail", "") or "").lower()
    if scoring_kind in _GOAL_KINDS:
        template_key = "risultati.gol"
    elif event_type == "card" and "red" in detail:
        template_key = "risultati.espulsione"
    else:
        return 0
    try:
        return _notify_owners(
            session,
            athlete_id=athlete_id,
            template_key=template_key,
            params={"minute": getattr(event, "minute_elapsed", None)},
            dedup_prefix=f"match_event:{event.id}",  # type: ignore[attr-defined]
        )
    except Exception:
        logger.warning("match_event_notification_failed", exc_info=True)
        return 0


def notify_availability(session: Session, *, availability: object) -> int:
    """Chiamata alla creazione di una ``PlayerAvailability`` (infortunio/squalifica)."""
    athlete_id = getattr(availability, "athlete_id", None)
    category = getattr(getattr(availability, "category", None), "value", None)
    if athlete_id is None or category not in {"injury", "suspension"}:
        return 0
    template_key = "risultati.infortunio" if category == "injury" else "risultati.squalifica"
    try:
        return _notify_owners(
            session,
            athlete_id=athlete_id,
            template_key=template_key,
            params={},
            dedup_prefix=f"availability:{availability.id}",  # type: ignore[attr-defined]
        )
    except Exception:
        logger.warning("availability_notification_failed", exc_info=True)
        return 0
