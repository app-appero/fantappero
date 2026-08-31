"""Unit tests for the fantasy_turns Celery beat schedule assembly."""

from __future__ import annotations

from fantasy_turns.schedule import fantasy_turns_beat_schedule


def test_both_entries_present_when_both_enabled() -> None:
    schedule = fantasy_turns_beat_schedule(
        enabled=True,
        interval_seconds=3600,
        full_refresh_enabled=True,
        full_refresh_interval_seconds=21_600,
    )
    assert schedule["fantasy-turns-ensure-upcoming"]["task"] == "fantasy_turns.ensure_upcoming"
    assert schedule["fantasy-turns-ensure-upcoming"]["schedule"] == 3600.0
    assert (
        schedule["fantasy-turns-refresh-full-calendar"]["task"]
        == "fantasy_turns.refresh_full_calendar_active_leagues"
    )
    assert schedule["fantasy-turns-refresh-full-calendar"]["schedule"] == 21_600.0


def test_ensure_upcoming_entry_omitted_when_disabled() -> None:
    schedule = fantasy_turns_beat_schedule(enabled=False, full_refresh_enabled=True)
    assert "fantasy-turns-ensure-upcoming" not in schedule
    assert "fantasy-turns-refresh-full-calendar" in schedule


def test_full_refresh_entry_omitted_when_disabled() -> None:
    schedule = fantasy_turns_beat_schedule(enabled=True, full_refresh_enabled=False)
    assert "fantasy-turns-ensure-upcoming" in schedule
    assert "fantasy-turns-refresh-full-calendar" not in schedule


def test_empty_schedule_when_both_disabled() -> None:
    assert fantasy_turns_beat_schedule(enabled=False, full_refresh_enabled=False) == {}
