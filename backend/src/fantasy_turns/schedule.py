"""Celery beat entries for automatic european turn generation."""

from __future__ import annotations


def fantasy_turns_beat_schedule(
    *,
    enabled: bool,
    interval_seconds: int = 3600,
) -> dict[str, dict]:
    if not enabled:
        return {}
    return {
        "fantasy-turns-ensure-upcoming": {
            "task": "fantasy_turns.ensure_upcoming",
            "schedule": float(interval_seconds),
            "options": {"expires": float(interval_seconds)},
        },
    }
