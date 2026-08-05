"""Auth and JWT configuration."""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator


class AuthSettingsMixin:
    """JWT, token expiry, and rate-limit knobs."""

    jwt_secret_key: SecretStr = Field(
        default=SecretStr("fantappero_local_jwt_dev_only_change_in_production"),
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=30,
        validation_alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS",
    )
    auth_email_verification_expire_hours: int = Field(
        default=24,
        validation_alias="AUTH_EMAIL_VERIFICATION_EXPIRE_HOURS",
    )
    auth_password_reset_expire_hours: int = Field(
        default=1,
        validation_alias="AUTH_PASSWORD_RESET_EXPIRE_HOURS",
    )
    auth_rate_limit_login_per_minute: int = Field(
        default=5,
        validation_alias="AUTH_RATE_LIMIT_LOGIN_PER_MINUTE",
    )
    auth_rate_limit_register_per_hour: int = Field(
        default=10,
        validation_alias="AUTH_RATE_LIMIT_REGISTER_PER_HOUR",
    )
    auth_rate_limit_forgot_password_per_hour: int = Field(
        default=3,
        validation_alias="AUTH_RATE_LIMIT_FORGOT_PASSWORD_PER_HOUR",
    )
    auth_rate_limit_resend_verification_per_hour: int = Field(
        default=3,
        validation_alias="AUTH_RATE_LIMIT_RESEND_VERIFICATION_PER_HOUR",
    )

    @field_validator(
        "jwt_access_token_expire_minutes",
        "jwt_refresh_token_expire_days",
        "auth_email_verification_expire_hours",
        "auth_password_reset_expire_hours",
        "auth_rate_limit_login_per_minute",
        "auth_rate_limit_register_per_hour",
        "auth_rate_limit_forgot_password_per_hour",
        "auth_rate_limit_resend_verification_per_hour",
        mode="before",
    )
    @classmethod
    def _parse_int(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value

    def resolved_jwt_secret(self) -> str:
        return self.jwt_secret_key.get_secret_value()
