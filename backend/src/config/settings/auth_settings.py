"""Auth and JWT configuration."""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator

#: Convenience default for a fresh local checkout — never valid outside dev/test
#: (see ``BaseAppSettings.secrets_must_be_explicit``). Used to sign access tokens
#: and the feedback-media links, so leaving it unchanged in production would let
#: anyone who reads this source forge a valid token for any user.
DEFAULT_JWT_SECRET = "fantappero_local_jwt_dev_only_change_in_production"


class AuthSettingsMixin:
    """JWT, token expiry, and rate-limit knobs."""

    jwt_secret_key: SecretStr = Field(
        default=SecretStr(DEFAULT_JWT_SECRET),
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=720,
        validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=30,
        validation_alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS",
    )
    auth_email_registration_enabled: bool = Field(
        default=True,
        validation_alias="AUTH_EMAIL_REGISTRATION_ENABLED",
        description=(
            "Permette di creare un account con email e password. Con `false` (pilota) si "
            "registra solo con Google; chi ha già un account con password continua ad accedere "
            "e il codice della registrazione con email resta, spento."
        ),
    )
    protected_operator_emails: str = Field(
        default="trottarosario@gmail.com",
        validation_alias="PROTECTED_OPERATOR_EMAILS",
        description=(
            "Indirizzi (separati da virgola) di operatori che non possono mai essere declassati, "
            "eliminati o messi in lista nera, nemmeno da un altro operatore."
        ),
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
    auth_rate_limit_google_login_per_minute: int = Field(
        default=10,
        validation_alias="AUTH_RATE_LIMIT_GOOGLE_LOGIN_PER_MINUTE",
    )
    google_oauth_client_ids: str = Field(
        default="",
        validation_alias="GOOGLE_OAUTH_CLIENT_IDS",
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
        "auth_rate_limit_google_login_per_minute",
        mode="before",
    )
    @classmethod
    def _parse_int(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value

    def resolved_jwt_secret(self) -> str:
        return self.jwt_secret_key.get_secret_value()

    def protected_operator_email_set(self) -> frozenset[str]:
        return frozenset(
            item.strip().lower()
            for item in self.protected_operator_emails.split(",")
            if item.strip()
        )

    def resolved_google_client_ids(self) -> list[str]:
        return [item.strip() for item in self.google_oauth_client_ids.split(",") if item.strip()]
