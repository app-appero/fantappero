"""Shared header and field names for correlation across API and workers."""

from __future__ import annotations

CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"
JOB_ID_HEADER = "X-Job-ID"

# Celery message header keys (lowercase; Celery normalizes custom headers).
CELERY_CORRELATION_ID_KEY = "correlation_id"
CELERY_REQUEST_ID_KEY = "request_id"
