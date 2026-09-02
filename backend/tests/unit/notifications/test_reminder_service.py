"""Unit tests for lineup reminder timezone formatting (EP09-02)."""

from __future__ import annotations

from datetime import UTC, datetime

from notifications.reminder_service import _format_local


def test_format_local_converts_utc_to_requested_timezone() -> None:
    moment = datetime(2026, 1, 15, 18, 30, tzinfo=UTC)
    assert _format_local(moment, "Europe/Rome") == "15/01/2026 19:30"


def test_format_local_falls_back_to_default_timezone_when_unknown() -> None:
    moment = datetime(2026, 1, 15, 18, 30, tzinfo=UTC)
    assert _format_local(moment, "Not/AZone") == _format_local(moment, "Europe/Rome")


def test_format_local_falls_back_to_default_timezone_when_missing() -> None:
    moment = datetime(2026, 1, 15, 18, 30, tzinfo=UTC)
    assert _format_local(moment, None) == _format_local(moment, "Europe/Rome")
