"""Shared mail configuration for API and worker processes."""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator


class MailSettingsMixin:
    """SMTP and outbound mail knobs."""

    smtp_host: str = Field(default="localhost", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: SecretStr | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(
        default=False,
        validation_alias="SMTP_USE_TLS",
        description="STARTTLS dopo la connessione in chiaro (tipicamente porta 587).",
    )
    smtp_use_ssl: bool = Field(
        default=False,
        validation_alias="SMTP_USE_SSL",
        description="TLS implicito fin dall'inizio della connessione (tipicamente porta 465).",
    )
    smtp_timeout_seconds: int = Field(default=30, validation_alias="SMTP_TIMEOUT_SECONDS")
    mail_transport: str = Field(
        default="auto",
        validation_alias="MAIL_TRANSPORT",
        description=(
            "`auto` (default): Resend se c'è RESEND_API_KEY, altrimenti SMTP. "
            "`resend`: solo Resend. `smtp`: solo SMTP, anche se la chiave Resend è impostata."
        ),
    )
    mail_fallback_to_smtp: bool = Field(
        default=False,
        validation_alias="MAIL_FALLBACK_TO_SMTP",
        description="Se l'invio con Resend fallisce e l'SMTP è configurato, riprova via SMTP.",
    )
    resend_api_key: SecretStr | None = Field(default=None, validation_alias="RESEND_API_KEY")
    mail_from: str = Field(default="noreply@fantappero.local", validation_alias="MAIL_FROM")
    mail_from_name: str = Field(default="FantApperò", validation_alias="MAIL_FROM_NAME")
    web_app_base_url: str = Field(
        default="http://localhost:5174",
        validation_alias="WEB_APP_BASE_URL",
    )

    @field_validator("smtp_port", "smtp_timeout_seconds", mode="before")
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

    def resolved_mail_transport(self) -> str:
        """`auto`, `resend` o `smtp`; qualunque altro valore è trattato come `auto`."""
        value = getattr(self, "mail_transport", "auto")
        text = value.strip().lower() if isinstance(value, str) else "auto"
        return text if text in {"auto", "resend", "smtp"} else "auto"

    def resolved_smtp_timeout(self) -> int:
        value = getattr(self, "smtp_timeout_seconds", 30)
        return value if isinstance(value, int) and value > 0 else 30

    def resolved_flag(self, name: str) -> bool:
        """Legge un'opzione booleana, `False` se non è un vero booleano (impostazioni parziali)."""
        return getattr(self, name, False) is True

    def is_smtp_configured(self) -> bool:
        """True se c'è un server SMTP reale (non il `localhost` di default dello sviluppo)."""
        host = (self.smtp_host or "").strip().lower()
        return host not in {"", "localhost", "127.0.0.1"} or bool(self.smtp_user)

    def resolved_smtp_password(self) -> str | None:
        if self.smtp_password is None:
            return None
        return self.smtp_password.get_secret_value()

    def resolved_resend_api_key(self) -> str | None:
        if self.resend_api_key is None:
            return None
        return self.resend_api_key.get_secret_value()
