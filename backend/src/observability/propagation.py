"""Create and propagate correlation IDs between API and workers."""

from __future__ import annotations

import uuid
from typing import Any

from observability.constants import (
    CELERY_CORRELATION_ID_KEY,
    CELERY_REQUEST_ID_KEY,
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
)
from observability.context import get_correlation_id, get_request_id, set_correlation_id


def new_id() -> str:
    return str(uuid.uuid4())


def ensure_correlation_id(existing: str | None = None) -> str:
    """Return an existing correlation ID or generate and bind a new one."""
    value = (existing or get_correlation_id() or "").strip() or new_id()
    set_correlation_id(value)
    return value


def extract_inbound_correlation(headers: dict[str, str]) -> str:
    """Read correlation ID from HTTP headers (case-insensitive map)."""
    lowered = {k.lower(): v for k, v in headers.items()}
    for key in (CORRELATION_ID_HEADER.lower(), REQUEST_ID_HEADER.lower()):
        raw = lowered.get(key)
        if raw and str(raw).strip():
            return str(raw).strip()
    return new_id()


def extract_inbound_request_id(headers: dict[str, str], *, fallback: str) -> str:
    lowered = {k.lower(): v for k, v in headers.items()}
    raw = lowered.get(REQUEST_ID_HEADER.lower())
    if raw and str(raw).strip():
        return str(raw).strip()
    return fallback


def celery_task_headers(
    *,
    correlation_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, str]:
    """Headers to pass into Celery ``apply_async(..., headers=...)``."""
    corr = ensure_correlation_id(correlation_id)
    req = (request_id or get_request_id() or corr).strip()
    return {
        CELERY_CORRELATION_ID_KEY: corr,
        CELERY_REQUEST_ID_KEY: req,
    }


def correlation_from_celery_headers(headers: dict[str, Any] | None) -> str | None:
    if not headers:
        return None
    for key in (CELERY_CORRELATION_ID_KEY, CORRELATION_ID_HEADER, "x-correlation-id"):
        value = headers.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def request_id_from_celery_headers(headers: dict[str, Any] | None) -> str | None:
    if not headers:
        return None
    for key in (CELERY_REQUEST_ID_KEY, REQUEST_ID_HEADER, "x-request-id"):
        value = headers.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None
