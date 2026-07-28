"""Celery worker for local stack health (EP01-02) with observability (EP01-05)."""

from __future__ import annotations

from celery import Celery

from config.settings.loader import validate_worker_settings
from observability.celery_signals import register_celery_observability
from observability.error_tracking import configure_error_tracking
from observability.logging import configure_logging

_worker_settings = validate_worker_settings()
configure_logging(_worker_settings.log_level)
configure_error_tracking(
    enabled=_worker_settings.error_tracking_enabled,
    dsn=_worker_settings.error_tracking_dsn,
)

celery_app = Celery("fantappero")
celery_app.conf.update(
    broker_url=_worker_settings.resolved_broker_url(),
    result_backend=_worker_settings.resolved_result_backend(),
    task_always_eager=False,
    broker_connection_retry_on_startup=True,
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
