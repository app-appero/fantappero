"""Celery tasks for periodic notification reminders (EP09-02) and push delivery (EP09-05)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings, validate_worker_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from notifications.expo_push_client import ExpoPushClient
from notifications.lock_reminder_service import LineupLockReminderService
from notifications.models import PushDevice
from notifications.push_send import send_to_devices
from notifications.reminder_service import LineupReminderService
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


@celery_app.task(name="notifications.send_lineup_reminders")
def send_lineup_reminders_task() -> dict[str, int]:
    """Remind fantasy teams with no lineup yet before their round's cutoff."""
    try:
        worker = validate_worker_settings()
        enabled = worker.notifications_lineup_reminder_enabled
        window_hours = worker.notifications_lineup_reminder_window_hours
    except Exception:
        api = get_api_settings()
        enabled = api.notifications_lineup_reminder_enabled
        window_hours = api.notifications_lineup_reminder_window_hours

    from system_jobs.service import allow_periodic

    if not allow_periodic("notifications-lineup-reminders", enabled):
        logger.info("notifications_lineup_reminder_skipped_disabled")
        return {"rounds_checked": 0, "rounds_with_pending_teams": 0, "reminders_sent": 0}

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            totals = LineupReminderService(session).send_due_reminders(
                now=datetime.now(UTC),
                window_hours=window_hours,
            )
    finally:
        engine.dispose()
    logger.info("notifications_lineup_reminder_task_done", extra=totals)
    return totals


@celery_app.task(name="notifications.send_lineup_lock_reminders")
def send_lineup_lock_reminders_task() -> dict[str, int]:
    """Warn before every upcoming per-player progressive lock instant.

    Distinct from ``send_lineup_reminders_task`` (one reminder per round,
    "save before the round closes"): this fires once per distinct lock
    instant (one or many players locking together), see
    ``notifications.lock_reminder_service``.
    """
    try:
        worker = validate_worker_settings()
        enabled = worker.notifications_lineup_lock_reminder_enabled
        window_minutes = worker.notifications_lineup_lock_reminder_window_minutes
    except Exception:
        api = get_api_settings()
        enabled = api.notifications_lineup_lock_reminder_enabled
        window_minutes = api.notifications_lineup_lock_reminder_window_minutes

    from system_jobs.service import allow_periodic

    if not allow_periodic("notifications-lineup-lock-reminders", enabled):
        logger.info("notifications_lineup_lock_reminder_skipped_disabled")
        return {"rounds_checked": 0, "teams_checked": 0, "reminders_sent": 0}

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            totals = LineupLockReminderService(session).send_due_reminders(
                now=datetime.now(UTC),
                window_minutes=window_minutes,
            )
    finally:
        engine.dispose()
    logger.info("notifications_lineup_lock_reminder_task_done", extra=totals)
    return totals


@celery_app.task(name="notifications.send_push")
def send_push_task(
    *,
    user_id: str,
    notification_id: str,
    title: str,
    body: str,
    deep_link: str | None,
    category: str,
) -> dict[str, int]:
    """Manda la push a tutti i dispositivi attivi dell'utente, revoca i token morti."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            devices = session.scalars(
                select(PushDevice).where(
                    PushDevice.user_id == UUID(user_id),
                    PushDevice.revoked_at.is_(None),
                )
            ).all()
            if not devices:
                return {"sent": 0, "revoked": 0}
            client = ExpoPushClient(
                base_url=settings.expo_push_base_url,
                access_token=settings.resolved_expo_push_access_token(),
                timeout_seconds=settings.expo_push_timeout_seconds,
            )
            try:
                result = send_to_devices(
                    session,
                    client,
                    list(devices),
                    title=title,
                    body=body,
                    data={
                        "notificationId": notification_id,
                        "deepLink": deep_link,
                        "category": category,
                    },
                )
            finally:
                client.close()
    finally:
        engine.dispose()
    get_metrics().incr(
        "notifications_push_sent_total", labels={"category": category}, amount=result["sent"]
    )
    if result["revoked"]:
        get_metrics().incr("notifications_push_revoked_total", amount=result["revoked"])
    logger.info("notifications_push_task_done", extra={"category": category, **result})
    return result


@celery_app.task(name="notifications.dispatch_broadcasts")
def dispatch_broadcasts_task() -> int:
    """Invia gli avvisi programmati dagli operatori il cui orario è arrivato."""
    from notifications.broadcast_service import dispatch_due
    from system_jobs.service import allow_periodic

    settings = get_api_settings()
    if not allow_periodic(
        "notifications-broadcast-dispatch", settings.notifications_broadcast_dispatch_enabled
    ):
        return 0
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            sent = dispatch_due(session, now=datetime.now(UTC))
    finally:
        engine.dispose()
    if sent:
        logger.info("notifications_broadcasts_dispatched", extra={"count": sent})
    return sent
