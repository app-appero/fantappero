"""Observability baseline: structured logs, correlation IDs, metrics, error tracking (EP01-05)."""

from __future__ import annotations

from observability.context import (
    clear_context,
    get_correlation_id,
    get_job_id,
    get_request_id,
    set_correlation_id,
    set_job_id,
    set_request_id,
)
from observability.error_tracking import ErrorTracker, get_error_tracker
from observability.logging import configure_logging, get_logger
from observability.metrics import MetricsRegistry, get_metrics
from observability.propagation import celery_task_headers, ensure_correlation_id

__all__ = [
    "ErrorTracker",
    "MetricsRegistry",
    "celery_task_headers",
    "clear_context",
    "configure_logging",
    "ensure_correlation_id",
    "get_correlation_id",
    "get_error_tracker",
    "get_job_id",
    "get_logger",
    "get_metrics",
    "get_request_id",
    "set_correlation_id",
    "set_job_id",
    "set_request_id",
]
