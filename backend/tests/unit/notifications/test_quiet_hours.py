"""Unit tests for the quiet-hours window check (EP09-05)."""

from __future__ import annotations

from datetime import UTC, datetime

from notifications.quiet_hours import is_within_quiet_hours


def test_no_bounds_configured_is_never_quiet() -> None:
    now = datetime(2026, 1, 15, 23, 0, tzinfo=UTC)
    assert (
        is_within_quiet_hours(now=now, timezone_name="Europe/Rome", start_hour=None, end_hour=None)
        is False
    )


def test_same_start_and_end_hour_is_never_quiet() -> None:
    now = datetime(2026, 1, 15, 23, 0, tzinfo=UTC)
    assert (
        is_within_quiet_hours(now=now, timezone_name="Europe/Rome", start_hour=9, end_hour=9)
        is False
    )


def test_simple_window_within_same_day() -> None:
    # Europe/Rome is UTC+1 in January -> 13:00 UTC is 14:00 local.
    inside = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
    outside = datetime(2026, 1, 15, 5, 0, tzinfo=UTC)
    assert (
        is_within_quiet_hours(now=inside, timezone_name="Europe/Rome", start_hour=13, end_hour=18)
        is True
    )
    assert (
        is_within_quiet_hours(now=outside, timezone_name="Europe/Rome", start_hour=13, end_hour=18)
        is False
    )


def test_window_wrapping_midnight() -> None:
    # 22:30 local (Europe/Rome, UTC+1) falls inside a 22 -> 8 window.
    late_night = datetime(2026, 1, 15, 21, 30, tzinfo=UTC)
    early_morning = datetime(2026, 1, 15, 6, 30, tzinfo=UTC)
    midday = datetime(2026, 1, 15, 11, 0, tzinfo=UTC)
    assert (
        is_within_quiet_hours(
            now=late_night, timezone_name="Europe/Rome", start_hour=22, end_hour=8
        )
        is True
    )
    assert (
        is_within_quiet_hours(
            now=early_morning, timezone_name="Europe/Rome", start_hour=22, end_hour=8
        )
        is True
    )
    assert (
        is_within_quiet_hours(now=midday, timezone_name="Europe/Rome", start_hour=22, end_hour=8)
        is False
    )


def test_unknown_timezone_falls_back_to_utc() -> None:
    now = datetime(2026, 1, 15, 13, 30, tzinfo=UTC)
    assert (
        is_within_quiet_hours(now=now, timezone_name="Not/AZone", start_hour=13, end_hour=18)
        is True
    )
