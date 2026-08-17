"""Fantasy turn auto-generation settings (EP06-01 follow-up)."""

from __future__ import annotations

from pydantic import Field, field_validator


class FantasyTurnsSettingsMixin:
    """Env knobs for automatic european turn generation."""

    fantasy_turns_auto_generate_enabled: bool = Field(
        default=True,
        validation_alias="FANTASY_TURNS_AUTO_GENERATE_ENABLED",
        description="When true, Celery beat ensures upcoming fantasy turns for active leagues.",
    )
    fantasy_turns_auto_generate_interval_seconds: int = Field(
        default=3600,
        validation_alias="FANTASY_TURNS_AUTO_GENERATE_INTERVAL_SECONDS",
        ge=300,
        le=86400,
        description="How often the ensure-upcoming task is enqueued (default hourly).",
    )
    fantasy_turns_horizon_days: int = Field(
        default=14,
        validation_alias="FANTASY_TURNS_HORIZON_DAYS",
        ge=1,
        le=60,
        description="How far ahead to materialize weekend/midweek turns.",
    )

    @field_validator("fantasy_turns_auto_generate_enabled", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        return value
