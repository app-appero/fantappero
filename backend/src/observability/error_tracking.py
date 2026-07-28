"""Error tracking behind a Protocol, gated by feature flag."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from observability.context import get_correlation_id, get_job_id, get_request_id
from observability.logging import get_logger
from observability.redact_logs import redact_log_mapping, redact_log_value

logger = get_logger(__name__)


@runtime_checkable
class ErrorTracker(Protocol):
    """Vendor-neutral error capture surface (Sentry-compatible later)."""

    def capture_exception(
        self,
        exc: BaseException,
        *,
        context: dict[str, Any] | None = None,
    ) -> None: ...

    def capture_message(self, message: str, *, level: str = "error") -> None: ...


class NullErrorTracker:
    """No-op tracker used when the feature flag is off."""

    def capture_exception(
        self,
        exc: BaseException,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        return None

    def capture_message(self, message: str, *, level: str = "error") -> None:
        return None


class LoggingErrorTracker:
    """Records errors as structured logs when enabled without an external DSN."""

    def capture_exception(
        self,
        exc: BaseException,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "error_type": type(exc).__name__,
            "error_message": redact_log_value(str(exc)),
            "correlation_id": get_correlation_id(),
            "request_id": get_request_id(),
            "job_id": get_job_id(),
        }
        if context:
            payload["context"] = redact_log_mapping(context)
        logger.error("error_tracked", extra=payload, exc_info=exc)

    def capture_message(self, message: str, *, level: str = "error") -> None:
        log_fn = getattr(logger, level.lower(), logger.error)
        log_fn(
            "error_tracked_message",
            extra={
                "tracked_message": redact_log_value(message),
                "correlation_id": get_correlation_id(),
                "request_id": get_request_id(),
                "job_id": get_job_id(),
            },
        )


_tracker: ErrorTracker = NullErrorTracker()


def get_error_tracker() -> ErrorTracker:
    return _tracker


def set_error_tracker(tracker: ErrorTracker) -> None:
    global _tracker
    _tracker = tracker


def configure_error_tracking(*, enabled: bool, dsn: str | None = None) -> ErrorTracker:
    """
    Wire the active tracker from settings.

    When ``enabled`` is false → NullErrorTracker.
    When ``enabled`` is true → LoggingErrorTracker until a vendor SDK is chosen.
    ``dsn`` is accepted for forward compatibility and must never be logged.
    """
    _ = dsn  # reserved for future vendor SDK; intentionally unused
    tracker: ErrorTracker = LoggingErrorTracker() if enabled else NullErrorTracker()
    set_error_tracker(tracker)
    return tracker
