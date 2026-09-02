"""Celery beat entries for periodic notification reminders (EP09-02)."""

from __future__ import annotations


def notifications_beat_schedule(
    *,
    enabled: bool,
    interval_seconds: int = 900,
) -> dict[str, dict]:
    if not enabled:
        return {}
    return {
        "notifications-lineup-reminders": {
            "task": "notifications.send_lineup_reminders",
            "schedule": float(interval_seconds),
            "options": {"expires": float(interval_seconds)},
        },
    }
