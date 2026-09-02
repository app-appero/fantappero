"""Celery beat entries for automatic european turn generation."""

from __future__ import annotations


def fantasy_turns_beat_schedule(
    *,
    enabled: bool,
    interval_seconds: int = 3600,
    full_refresh_enabled: bool = True,
    full_refresh_interval_seconds: int = 21_600,
) -> dict[str, dict]:
    schedule: dict[str, dict] = {}
    if enabled:
        schedule["fantasy-turns-ensure-upcoming"] = {
            "task": "fantasy_turns.ensure_upcoming",
            "schedule": float(interval_seconds),
            "options": {"expires": float(interval_seconds)},
        }
    if full_refresh_enabled:
        schedule["fantasy-turns-refresh-full-calendar"] = {
            "task": "fantasy_turns.refresh_full_calendar_active_leagues",
            "schedule": float(full_refresh_interval_seconds),
            "options": {"expires": float(full_refresh_interval_seconds)},
        }
    return schedule
