"""Shared mail configuration for API and worker processes."""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator


class MailSettingsMixin:
    """SMTP and outbound mail knobs."""

    smtp_host: str = Field(default="localhost", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: SecretStr | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=False, validation_alias="SMTP_USE_TLS")
    mail_from: str = Field(default="noreply@fantappero.local", validation_alias="MAIL_FROM")
    mail_from_name: str = Field(default="FantApperò", validation_alias="MAIL_FROM_NAME")
    web_app_base_url: str = Field(
        default="http://localhost:5174",
        validation_alias="WEB_APP_BASE_URL",
    )

    @field_validator("smtp_port", mode="before")
    @classmethod
    def _parse_port(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value

    @field_validator("smtp_user", "mail_from", "mail_from_name", "web_app_base_url", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if value is None:
            return None
        return str(value).strip()

    def resolved_smtp_password(self) -> str | None:
        if self.smtp_password is None:
            return None
        return self.smtp_password.get_secret_value()
