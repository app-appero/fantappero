"""Notification reminder settings (EP09-02)."""

from __future__ import annotations

from pydantic import Field, field_validator


class NotificationsSettingsMixin:
    """Env knobs for the periodic in-app reminder tasks."""

    notifications_lineup_reminder_enabled: bool = Field(
        default=True,
        validation_alias="NOTIFICATIONS_LINEUP_REMINDER_ENABLED",
        description="When true, Celery beat sends lineup-deadline reminders before cutoff.",
    )
    notifications_lineup_reminder_interval_seconds: int = Field(
        default=900,
        validation_alias="NOTIFICATIONS_LINEUP_REMINDER_INTERVAL_SECONDS",
        ge=60,
        le=86400,
        description="How often the reminder task is enqueued (default every 15 minutes).",
    )
    notifications_lineup_reminder_window_hours: int = Field(
        default=24,
        validation_alias="NOTIFICATIONS_LINEUP_REMINDER_WINDOW_HOURS",
        ge=1,
        le=168,
        description="How far ahead of cutoff a team without a lineup is reminded.",
    )

    @field_validator("notifications_lineup_reminder_enabled", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        return value
