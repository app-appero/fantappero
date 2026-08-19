"""Celery tasks for periodic notification reminders (EP09-02)."""

from __future__ import annotations

from datetime import UTC, datetime

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings, validate_worker_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from notifications.reminder_service import LineupReminderService
from observability.logging import get_logger

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

    if not enabled:
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
