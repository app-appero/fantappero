"""Request/job correlation context stored in contextvars."""

from __future__ import annotations

from contextvars import ContextVar, Token

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_request_id() -> str | None:
    return _request_id.get()


def get_job_id() -> str | None:
    return _job_id.get()


def set_correlation_id(value: str | None) -> Token[str | None]:
    return _correlation_id.set(value)


def set_request_id(value: str | None) -> Token[str | None]:
    return _request_id.set(value)


def set_job_id(value: str | None) -> Token[str | None]:
    return _job_id.set(value)


def clear_context() -> None:
    """Reset all observability context (tests and task teardown)."""
    _correlation_id.set(None)
    _request_id.set(None)
    _job_id.set(None)


def bind_ids(
    *,
    correlation_id: str | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
) -> tuple[Token[str | None], Token[str | None], Token[str | None]]:
    """Set IDs and return tokens for optional restore."""
    return (
        set_correlation_id(correlation_id),
        set_request_id(request_id),
        set_job_id(job_id),
    )
