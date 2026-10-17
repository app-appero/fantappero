"""Season-wide sports data sync settings (catalog + fixtures bulk sync).

Senza questo giro periodico, catalogo e calendario fixture restano vuoti
finché un operatore non li sincronizza a mano — e la creazione di una lega
per una nuova stagione trova zero Turni Europei materializzabili finché
qualcuno non lo fa. Questi job girano indipendentemente da qualunque lega.
"""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator


class SportsDataSyncSettingsMixin:
    """Env knobs for periodic season-wide catalog/fixtures sync."""

    sports_data_catalog_sync_enabled: bool = Field(
        default=True,
        validation_alias="SPORTS_DATA_CATALOG_SYNC_ENABLED",
        description=(
            "When true, Celery beat periodically syncs the MVP competitions "
            "catalog (seasons, is_current flag, clubs)."
        ),
    )
    sports_data_catalog_sync_interval_seconds: int = Field(
        default=86_400,
        validation_alias="SPORTS_DATA_CATALOG_SYNC_INTERVAL_SECONDS",
        ge=3600,
        le=604_800,
        description="How often the MVP catalog sync is enqueued (default daily).",
    )
    sports_data_fixtures_sync_enabled: bool = Field(
        default=True,
        validation_alias="SPORTS_DATA_FIXTURES_SYNC_ENABLED",
        description=(
            "When true, Celery beat periodically syncs the season fixture "
            "calendar for MVP competitions."
        ),
    )
    sports_data_fixtures_sync_interval_seconds: int = Field(
        default=259_200,
        validation_alias="SPORTS_DATA_FIXTURES_SYNC_INTERVAL_SECONDS",
        ge=3600,
        le=604_800,
        description="How often the MVP fixtures calendar sync is enqueued (default every 3 days).",
    )
    predicted_lineups_enabled: bool = Field(
        default=True,
        validation_alias="PREDICTED_LINEUPS_ENABLED",
        description="When true, Celery beat refreshes FotMob probable lineups once a day.",
    )
    predicted_lineups_interval_seconds: int = Field(
        default=86_400,
        validation_alias="PREDICTED_LINEUPS_INTERVAL_SECONDS",
        ge=3600,
        le=604_800,
        description="How often probable lineups are refreshed (default daily).",
    )
    rapidapi_key: SecretStr | None = Field(
        default=None,
        validation_alias="RAPIDAPI_KEY",
        description="RapidAPI key for FotMob. Never logged or returned to clients.",
    )
    fotmob_base_url: str = Field(
        default="https://fotmob-api.p.rapidapi.com",
        validation_alias="FOTMOB_BASE_URL",
    )
    fotmob_timeout_seconds: float = Field(
        default=20.0,
        validation_alias="FOTMOB_TIMEOUT_SECONDS",
        ge=1.0,
        le=60.0,
    )
    fotmob_max_retries: int = Field(
        default=2,
        validation_alias="FOTMOB_MAX_RETRIES",
        ge=0,
        le=5,
    )
    fotmob_max_lineup_calls: int = Field(
        default=40,
        validation_alias="FOTMOB_MAX_LINEUP_CALLS",
        ge=1,
        le=200,
        description="Cap of lineup requests per sync run.",
    )
    predicted_lineups_min_age_hours: int = Field(
        default=20,
        validation_alias="PREDICTED_LINEUPS_MIN_AGE_HOURS",
        ge=1,
        le=72,
        description=(
            "Skip a fixture whose latest snapshot is newer than this, unless the run is manual."
        ),
    )
    soccer_oracle_base_url: str | None = Field(
        default=None,
        validation_alias="SOCCER_ORACLE_BASE_URL",
        description="Base URL of the Soccer-Oracle players API. Unset disables the integration.",
    )
    soccer_oracle_players_key: SecretStr | None = Field(
        default=None,
        validation_alias="SOCCER_ORACLE_PLAYERS_KEY",
        description="X-Service-Key for the Soccer-Oracle players API. Never logged or returned.",
    )
    soccer_oracle_timeout_seconds: float = Field(
        default=5.0,
        validation_alias="SOCCER_ORACLE_TIMEOUT_SECONDS",
        ge=1.0,
        le=30.0,
    )
    soccer_oracle_max_retries: int = Field(
        default=1,
        validation_alias="SOCCER_ORACLE_MAX_RETRIES",
        ge=0,
        le=3,
    )
    soccer_oracle_min_confidence: float = Field(
        default=0.6,
        validation_alias="SOCCER_ORACLE_MIN_CONFIDENCE",
        ge=0.0,
        le=1.0,
        description=(
            "Minimum Soccer-Oracle mapping confidence to trust for probable-lineup hints."
        ),
    )

    @field_validator("rapidapi_key", mode="before")
    @classmethod
    def _blank_rapidapi_key(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("soccer_oracle_base_url", mode="before")
    @classmethod
    def _blank_soccer_oracle_base_url(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("soccer_oracle_players_key", mode="before")
    @classmethod
    def _blank_soccer_oracle_key(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def resolved_rapidapi_key(self) -> str | None:
        if self.rapidapi_key is None:
            return None
        value = self.rapidapi_key.get_secret_value().strip()
        return value or None

    def resolved_soccer_oracle_key(self) -> str | None:
        if self.soccer_oracle_players_key is None:
            return None
        value = self.soccer_oracle_players_key.get_secret_value().strip()
        return value or None

    @field_validator(
        "sports_data_catalog_sync_enabled",
        "sports_data_fixtures_sync_enabled",
        "predicted_lineups_enabled",
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
