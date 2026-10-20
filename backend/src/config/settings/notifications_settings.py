"""Notification reminder settings (EP09-02) and push delivery (EP09-05)."""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator


class NotificationsSettingsMixin:
    """Env knobs for the periodic in-app reminder tasks and push delivery."""

    notifications_push_enabled: bool = Field(
        default=True,
        validation_alias="NOTIFICATIONS_PUSH_ENABLED",
        description="When true, a created notification also triggers an Expo push send.",
    )
    expo_push_base_url: str = Field(
        default="https://exp.host/--/api/v2/push/send",
        validation_alias="EXPO_PUSH_BASE_URL",
    )
    expo_push_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="EXPO_PUSH_ACCESS_TOKEN",
        description=(
            "Optional enhanced-security token for Expo push. Never logged or returned."
        ),
    )
    expo_push_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="EXPO_PUSH_TIMEOUT_SECONDS",
        ge=1.0,
        le=30.0,
    )

    @field_validator("expo_push_access_token", mode="before")
    @classmethod
    def _blank_expo_push_access_token(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def resolved_expo_push_access_token(self) -> str | None:
        if self.expo_push_access_token is None:
            return None
        value = self.expo_push_access_token.get_secret_value().strip()
        return value or None

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

    @field_validator(
        "notifications_push_enabled",
        "notifications_lineup_reminder_enabled",
        mode="before",
    )
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        return value
