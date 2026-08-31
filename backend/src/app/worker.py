"""Celery worker for local stack health (EP01-02) with observability (EP01-05)."""

from __future__ import annotations

from celery import Celery

from config.settings.loader import validate_worker_settings
from fantasy_lineups.schedule import ai_lineups_beat_schedule
from fantasy_turns.schedule import fantasy_turns_beat_schedule
from notifications.schedule import notifications_beat_schedule
from observability.celery_signals import register_celery_observability
from observability.error_tracking import configure_error_tracking
from observability.logging import configure_logging
from sports_data.scheduler.policy import beat_schedule_entries

_worker_settings = validate_worker_settings()
configure_logging(_worker_settings.log_level)
configure_error_tracking(
    enabled=_worker_settings.error_tracking_enabled,
    dsn=_worker_settings.error_tracking_dsn,
)

_beat_schedule: dict = {}
_beat_schedule.update(
    beat_schedule_entries(
        enabled=_worker_settings.sports_scheduler_enabled,
        live_interval=_worker_settings.sports_poll_live_interval_seconds,
        pre_interval=_worker_settings.sports_poll_pre_interval_seconds,
        post_interval=_worker_settings.sports_poll_post_interval_seconds,
        late_interval=_worker_settings.sports_poll_late_interval_seconds,
    )
)
_beat_schedule.update(
    fantasy_turns_beat_schedule(
        enabled=_worker_settings.fantasy_turns_auto_generate_enabled,
        interval_seconds=_worker_settings.fantasy_turns_auto_generate_interval_seconds,
        full_refresh_enabled=_worker_settings.fantasy_turns_full_refresh_enabled,
        full_refresh_interval_seconds=_worker_settings.fantasy_turns_full_refresh_interval_seconds,
    )
)
_beat_schedule.update(
    ai_lineups_beat_schedule(
        enabled=_worker_settings.ai_lineups_auto_generate_enabled,
        interval_seconds=_worker_settings.ai_lineups_auto_generate_interval_seconds,
    )
)
_beat_schedule.update(
    notifications_beat_schedule(
        enabled=_worker_settings.notifications_lineup_reminder_enabled,
        interval_seconds=_worker_settings.notifications_lineup_reminder_interval_seconds,
    )
)

celery_app = Celery("fantappero")
celery_app.conf.update(
    broker_url=_worker_settings.resolved_broker_url(),
    result_backend=_worker_settings.resolved_result_backend(),
    task_always_eager=_worker_settings.fantappero_env.value == "test",
    broker_connection_retry_on_startup=True,
    beat_schedule=_beat_schedule,
)
register_celery_observability(celery_app)


@celery_app.task(name="app.worker.ping")
def ping() -> str:
    """Lightweight task used by smoke tests."""
    return "pong"


@celery_app.task(name="app.worker.fail")
def fail() -> None:
    """Task that always fails — used by observability unit tests."""
    raise RuntimeError("intentional_job_failure")


# Register task modules for the worker process (import side effects).
import admin.listone_tasks  # noqa: E402, F401
import fantasy_lineups.tasks  # noqa: E402, F401
import fantasy_ratings.tasks  # noqa: E402, F401
import fantasy_turns.tasks  # noqa: E402, F401
import leagues.listone_tasks  # noqa: E402, F401
import mail.tasks  # noqa: E402, F401
import notifications.tasks  # noqa: E402, F401
import sports_data.catalog.tasks  # noqa: E402, F401
import sports_data.fixtures.tasks  # noqa: E402, F401
import sports_data.listone.tasks  # noqa: E402, F401
import sports_data.quality.tasks  # noqa: E402, F401
import sports_data.roster.tasks  # noqa: E402, F401
import sports_data.scheduler.tasks  # noqa: E402, F401
