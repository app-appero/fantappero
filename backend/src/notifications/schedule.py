"""Celery beat entries for periodic notification reminders (EP09-02)."""

from __future__ import annotations


def notifications_beat_schedule(
    *,
    enabled: bool,
    interval_seconds: int = 900,
    broadcast_enabled: bool = False,
    broadcast_interval_seconds: int = 60,
) -> dict[str, dict]:
    schedule: dict[str, dict] = {}
    if broadcast_enabled:
        schedule["notifications-broadcast-dispatch"] = {
            "task": "notifications.dispatch_broadcasts",
            "schedule": float(broadcast_interval_seconds),
            "options": {"expires": float(broadcast_interval_seconds)},
        }
    if not enabled:
        return schedule
    schedule.update({
        "notifications-lineup-reminders": {
            "task": "notifications.send_lineup_reminders",
            "schedule": float(interval_seconds),
            "options": {"expires": float(interval_seconds)},
        },
    })
    return schedule
