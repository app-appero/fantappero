"""Auth settings consumed by the API service."""

from __future__ import annotations

from pydantic import Field, SecretStr

from config.settings.base import BaseAppSettings


class AuthSettings(BaseAppSettings):
    """Session, token, and rate-limit configuration."""

    auth_session_ttl_seconds: int = Field(
        default=60 * 60 * 24 * 7,
        validation_alias="AUTH_SESSION_TTL_SECONDS",
        ge=60,
    )
    auth_one_time_token_ttl_seconds: int = Field(
        default=60 * 60,
        validation_alias="AUTH_ONE_TIME_TOKEN_TTL_SECONDS",
        ge=60,
    )
    auth_rate_limit_max_attempts: int = Field(
        default=5,
        validation_alias="AUTH_RATE_LIMIT_MAX_ATTEMPTS",
        ge=1,
    )
    auth_rate_limit_window_seconds: int = Field(
        default=900,
        validation_alias="AUTH_RATE_LIMIT_WINDOW_SECONDS",
        ge=60,
    )
    auth_public_base_url: str = Field(
        default="http://127.0.0.1:5173",
        validation_alias="AUTH_PUBLIC_BASE_URL",
        description="Client base URL embedded in verification/reset links.",
    )
    auth_secret_key: SecretStr | None = Field(
        default=None,
        validation_alias="AUTH_SECRET_KEY",
        description="Reserved for future signed tokens; optional in EP02-01.",
    )
