"""Typed environment schema for the FastAPI process."""

from __future__ import annotations

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings.auth_settings import AuthSettingsMixin
from config.settings.base import BaseAppSettings, require_non_empty
from config.settings.fantasy_turns_settings import FantasyTurnsSettingsMixin
from config.settings.mail import MailSettingsMixin
from config.settings.profile_settings import ProfileSettingsMixin
from config.settings.scheduler_settings import SportsSchedulerSettingsMixin


class ApiSettings(
    BaseAppSettings,
    AuthSettingsMixin,
    MailSettingsMixin,
    ProfileSettingsMixin,
    SportsSchedulerSettingsMixin,
    FantasyTurnsSettingsMixin,
):
    """Configuration consumed by the API service."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")

    api_football_key: SecretStr | None = Field(
        default=None,
        validation_alias="API_FOOTBALL_KEY",
        description="Provider key — backend/scripts only; never exposed to clients.",
    )
    apisports_key: SecretStr | None = Field(
        default=None,
        validation_alias="APISPORTS_KEY",
        description="Alternate name for API_FOOTBALL_KEY.",
    )
    api_football_base_url: str = Field(
        default="https://v3.football.api-sports.io",
        validation_alias="API_FOOTBALL_BASE_URL",
        description="API-Football v3 base URL (SPD adapter only).",
    )
    api_football_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="API_FOOTBALL_TIMEOUT_SECONDS",
        ge=1.0,
        le=120.0,
    )
    api_football_max_retries: int = Field(
        default=3,
        validation_alias="API_FOOTBALL_MAX_RETRIES",
        ge=0,
        le=10,
    )
    api_football_retry_backoff_seconds: float = Field(
        default=1.0,
        validation_alias="API_FOOTBALL_RETRY_BACKOFF_SECONDS",
        ge=0.0,
        le=60.0,
    )
    api_football_requests_per_minute: int = Field(
        default=300,
        validation_alias="API_FOOTBALL_REQUESTS_PER_MINUTE",
        ge=1,
        le=1200,
        description="Client throttle aligned to plan minute quota (Pro=300).",
    )
    api_football_rate_limit_pause_seconds: float = Field(
        default=60.0,
        validation_alias="API_FOOTBALL_RATE_LIMIT_PAUSE_SECONDS",
        ge=1.0,
        le=300.0,
        description="Pause before resume when provider returns 429 / rateLimit body.",
    )

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def _strip_or_none(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def _require_infra_when_strict(self) -> ApiSettings:
        if not self.strict_infra_required:
            return self
        require_non_empty("DATABASE_URL", self.database_url)
        require_non_empty("REDIS_URL", self.redis_url)
        return self

    def resolved_api_football_key(self) -> str | None:
        if self.api_football_key is not None:
            return self.api_football_key.get_secret_value()
        if self.apisports_key is not None:
            return self.apisports_key.get_secret_value()
        return None


class WebPublicSettings(BaseAppSettings):
    """Documented public env vars for the web client (validated in apps/web)."""

    vite_api_base_url: HttpUrl | str = Field(
        default="http://127.0.0.1:8001",
        validation_alias="VITE_API_BASE_URL",
    )


class MobilePublicSettings(BaseAppSettings):
    """Documented public env vars for the mobile client (validated in apps/mobile)."""

    expo_public_api_base_url: HttpUrl | str = Field(
        default="http://127.0.0.1:8001",
        validation_alias="EXPO_PUBLIC_API_BASE_URL",
    )
