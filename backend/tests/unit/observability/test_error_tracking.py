"""Error tracker feature flag wiring."""

from __future__ import annotations

from observability.error_tracking import (
    LoggingErrorTracker,
    NullErrorTracker,
    configure_error_tracking,
    get_error_tracker,
    set_error_tracker,
)


def teardown_function() -> None:
    set_error_tracker(NullErrorTracker())


def test_feature_flag_off_uses_null_tracker() -> None:
    tracker = configure_error_tracking(enabled=False, dsn="https://secret@example/1")
    assert isinstance(tracker, NullErrorTracker)
    assert isinstance(get_error_tracker(), NullErrorTracker)
    # Must not raise / leak
    tracker.capture_exception(RuntimeError("x"), context={"token": "abc"})


def test_feature_flag_on_uses_logging_tracker() -> None:
    tracker = configure_error_tracking(enabled=True, dsn=None)
    assert isinstance(tracker, LoggingErrorTracker)
