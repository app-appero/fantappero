"""Shared sports scheduler configuration (EP04-06)."""

from __future__ import annotations

from pydantic import Field, field_validator


class SportsSchedulerSettingsMixin:
    """Env knobs for Celery beat polling of match windows."""

    sports_scheduler_enabled: bool = Field(
        default=False,
        validation_alias="SPORTS_SCHEDULER_ENABLED",
        description="When true, Celery beat enqueues pre/live/post/late poll tasks.",
    )
    sports_poll_live_interval_seconds: int = Field(
        default=60,
        validation_alias="SPORTS_POLL_LIVE_INTERVAL_SECONDS",
        ge=15,
        le=3600,
    )
    sports_poll_pre_interval_seconds: int = Field(
        default=900,
        validation_alias="SPORTS_POLL_PRE_INTERVAL_SECONDS",
        ge=60,
        le=7200,
    )
    sports_poll_post_interval_seconds: int = Field(
        default=600,
        validation_alias="SPORTS_POLL_POST_INTERVAL_SECONDS",
        ge=60,
        le=7200,
    )
    sports_poll_late_interval_seconds: int = Field(
        default=3600,
        validation_alias="SPORTS_POLL_LATE_INTERVAL_SECONDS",
        ge=300,
        le=86400,
    )

    @field_validator("sports_scheduler_enabled", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        return value
