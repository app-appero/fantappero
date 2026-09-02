"""Structured JSON logging with correlation IDs and redaction."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from observability.context import get_correlation_id, get_job_id, get_request_id
from observability.redact_logs import redact_log_mapping, redact_log_value


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record (UTC timestamps)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_log_value(record.getMessage()),
        }
        correlation_id = get_correlation_id()
        request_id = get_request_id()
        job_id = get_job_id()
        if correlation_id:
            payload["correlation_id"] = correlation_id
        if request_id:
            payload["request_id"] = request_id
        if job_id:
            payload["job_id"] = job_id

        extras = getattr(record, "observability_extra", None)
        if isinstance(extras, dict) and extras:
            payload.update(redact_log_mapping(extras))

        if record.exc_info:
            payload["exc_info"] = redact_log_value(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", *, stream: Any | None = None) -> None:
    """Configure root logger for JSON output. Safe to call multiple times."""
    root = logging.getLogger()
    numeric = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric)

    handler: logging.Handler | None = None
    for existing in root.handlers:
        if getattr(existing, "_fantappero_json", False):
            handler = existing
            break

    if handler is None:
        handler = logging.StreamHandler(stream or sys.stderr)
        handler._fantappero_json = True  # type: ignore[attr-defined]
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    else:
        handler.setFormatter(JsonFormatter())

    handler.setLevel(numeric)


def get_logger(name: str) -> logging.LoggerAdapter[logging.Logger]:
    """Return a logger that accepts ``extra=`` dicts bound into JSON fields."""

    class _Adapter(logging.LoggerAdapter[logging.Logger]):
        def process(self, msg: Any, kwargs: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
            extra = kwargs.pop("extra", None) or {}
            if not isinstance(extra, dict):
                extra = {"extra": extra}
            record_extra = kwargs.setdefault("extra", {})
            record_extra["observability_extra"] = extra
            return msg, kwargs

    return _Adapter(logging.getLogger(name), {})
