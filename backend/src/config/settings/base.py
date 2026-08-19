"""Shared settings primitives."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FantapperoEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class BaseAppSettings(BaseSettings):
    """Common environment knobs for backend processes."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    fantappero_env: FantapperoEnv = Field(
        default=FantapperoEnv.DEVELOPMENT,
        validation_alias="FANTAPPERO_ENV",
        description="Runtime environment profile (development, test, staging, production).",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )

    error_tracking_enabled: bool = Field(
        default=False,
        validation_alias="ERROR_TRACKING_ENABLED",
        description="Feature flag: capture exceptions via ErrorTracker interface.",
    )
    error_tracking_dsn: str | None = Field(
        default=None,
        validation_alias="ERROR_TRACKING_DSN",
        description="Optional vendor DSN; never log this value.",
    )

    @property
    def strict_infra_required(self) -> bool:
        """When true, DATABASE_URL / REDIS_URL / Celery URLs must be present."""
        return self.fantappero_env is not FantapperoEnv.TEST

    @field_validator("fantappero_env", mode="before")
    @classmethod
    def _normalize_env(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("error_tracking_dsn", mode="before")
    @classmethod
    def _strip_dsn_or_none(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


def require_non_empty(name: str, value: str | None) -> str:
    if value is None or not str(value).strip():
        msg = f"Missing required environment variable: {name}"
        raise ValueError(msg)
    return str(value).strip()
