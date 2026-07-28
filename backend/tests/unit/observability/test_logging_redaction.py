"""JSON log format and secret/PII redaction."""

from __future__ import annotations

import io
import json
import logging

from observability.context import clear_context, set_correlation_id, set_job_id, set_request_id
from observability.logging import JsonFormatter, get_logger
from observability.redact_logs import redact_log_mapping, redact_log_value


def setup_function() -> None:
    clear_context()


def test_json_log_includes_correlation_ids() -> None:
    stream = io.StringIO()
    logger_name = "test.observability.logs"
    target = logging.getLogger(logger_name)
    target.handlers.clear()
    target.setLevel(logging.INFO)
    target.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    target.addHandler(handler)

    set_correlation_id("c-1")
    set_request_id("r-1")
    set_job_id("j-1")

    logger = get_logger(logger_name)
    logger.info("hello", extra={"path": "/ready", "email": "user@example.com"})
    handler.flush()

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert lines
    payload = json.loads(lines[-1])
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["correlation_id"] == "c-1"
    assert payload["request_id"] == "r-1"
    assert payload["job_id"] == "j-1"
    assert payload["path"] == "/ready"
    assert payload["email"] == "***REDACTED***"
    assert "timestamp" in payload

    target.handlers.clear()


def test_redact_secrets_in_log_values() -> None:
    text = "DATABASE_URL=postgresql://fantappero:supersecret@db/fantappero"
    redacted = redact_log_value(text)
    assert "supersecret" not in redacted
    assert "***REDACTED***" in redacted


def test_redact_pii_keys_in_mapping() -> None:
    payload = {
        "phone": "+393331112233",
        "status": "ok",
        "nested": {"fiscal_code": "RSSMRA80A01H501U", "score": 1},
        "token": "tok_abcdefghijklmnopqrst",
    }
    redacted = redact_log_mapping(payload)
    assert redacted["phone"] == "***REDACTED***"
    assert redacted["status"] == "ok"
    assert redacted["nested"]["fiscal_code"] == "***REDACTED***"
    assert redacted["nested"]["score"] == 1
    assert redacted["token"] == "***REDACTED***"


def test_formatter_redacts_message_secrets() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="t",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="password= hunter2 leaked",
        args=(),
        exc_info=None,
    )
    rendered = formatter.format(record)
    payload = json.loads(rendered)
    assert "hunter2" not in payload["message"]
