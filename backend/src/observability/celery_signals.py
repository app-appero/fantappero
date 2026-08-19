"""Celery signal hooks for correlation IDs, job metrics, and error tracking."""

from __future__ import annotations

import time
from typing import Any

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun

from observability.context import clear_context, set_correlation_id, set_job_id, set_request_id
from observability.error_tracking import get_error_tracker
from observability.logging import get_logger
from observability.metrics import (
    JOB_DURATION_SECONDS,
    JOBS_FAILED_TOTAL,
    JOBS_TOTAL,
    QUEUE_DEPTH,
    get_metrics,
)
from observability.propagation import (
    correlation_from_celery_headers,
    ensure_correlation_id,
    new_id,
    request_id_from_celery_headers,
)

logger = get_logger(__name__)

_task_starts: dict[str, float] = {}


def _headers_from_task(task: Any) -> dict[str, Any]:
    request = getattr(task, "request", None)
    if request is None:
        return {}
    headers = getattr(request, "headers", None) or {}
    return headers if isinstance(headers, dict) else {}


def _task_name(task: Any, sender: Any = None) -> str:
    for candidate in (task, sender):
        name = getattr(candidate, "name", None)
        if name:
            return str(name)
    return "unknown"


@task_prerun.connect
def _on_task_prerun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    **_extra: Any,
) -> None:
    headers = _headers_from_task(task)
    correlation = correlation_from_celery_headers(headers) or ensure_correlation_id()
    request_id = request_id_from_celery_headers(headers) or correlation
    job_id = task_id or new_id()
    set_correlation_id(correlation)
    set_request_id(request_id)
    set_job_id(job_id)
    if task_id:
        _task_starts[task_id] = time.perf_counter()
    logger.info(
        "job_started",
        extra={"task": _task_name(task, sender), "job_id": job_id},
    )


@task_postrun.connect
def _on_task_postrun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    state: str | None = None,
    **_extra: Any,
) -> None:
    task_name = _task_name(task, sender)
    resolved_state = state or "SUCCESS"
    metrics = get_metrics()
    metrics.incr(JOBS_TOTAL, labels={"task": task_name, "state": resolved_state})
    if task_id and task_id in _task_starts:
        elapsed = time.perf_counter() - _task_starts.pop(task_id)
        metrics.observe(JOB_DURATION_SECONDS, elapsed, labels={"task": task_name})
    logger.info(
        "job_completed",
        extra={"task": task_name, "state": resolved_state},
    )
    clear_context()


@task_failure.connect
def _on_task_failure(
    sender: Any = None,
    task_id: str | None = None,
    exception: BaseException | None = None,
    **_extra: Any,
) -> None:
    # Runs before task_postrun; do not clear context or double-count JOBS_TOTAL here.
    task_name = _task_name(sender)
    get_metrics().incr(JOBS_FAILED_TOTAL, labels={"task": task_name})
    if exception is not None:
        get_error_tracker().capture_exception(
            exception,
            context={"task": task_name, "job_id": task_id},
        )
    logger.error(
        "job_failed",
        extra={
            "task": task_name,
            "error_type": type(exception).__name__ if exception else "unknown",
        },
        exc_info=exception is not None,
    )


def register_celery_observability(app: Celery) -> None:
    """
    Public hook workers call after creating the Celery app.

    Signal handlers connect at import time; this attaches a best-effort
    queue-depth sampler on the app instance.
    """

    def _sample_queue_depth() -> None:
        try:
            with app.connection_or_acquire() as conn:
                client = getattr(conn.default_channel, "client", None)
                if client is None:
                    return
                depth = client.llen("celery")
                get_metrics().set_gauge(QUEUE_DEPTH, float(depth), labels={"queue": "celery"})
        except Exception:  # noqa: BLE001 — best-effort gauge
            logger.info("queue_depth_unavailable", extra={"queue": "celery"})

    app.sample_queue_depth = _sample_queue_depth  # type: ignore[attr-defined]
