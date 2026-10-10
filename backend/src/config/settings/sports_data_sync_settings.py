"""Season-wide sports data sync settings (catalog + fixtures bulk sync).

Senza questo giro periodico, catalogo e calendario fixture restano vuoti
finché un operatore non li sincronizza a mano — e la creazione di una lega
per una nuova stagione trova zero Turni Europei materializzabili finché
qualcuno non lo fa. Questi job girano indipendentemente da qualunque lega.
"""

from __future__ import annotations

from pydantic import Field, field_validator


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

    @field_validator(
        "sports_data_catalog_sync_enabled",
        "sports_data_fixtures_sync_enabled",
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
