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
    # Formazione automatica IA (EP13-P05 / ADR-0005). Le squadre IA
    # partecipano al pilot reale, quindi il default è attivo.
    ai_lineups_auto_generate_enabled: bool = Field(
        default=True,
        validation_alias="AI_LINEUPS_AUTO_GENERATE_ENABLED",
        description="When true, Celery beat fields AI managers' lineups for open turns.",
    )
    ai_lineups_auto_generate_interval_seconds: int = Field(
        default=1800,
        validation_alias="AI_LINEUPS_AUTO_GENERATE_INTERVAL_SECONDS",
        ge=300,
        le=86400,
        description="How often the AI lineup task is enqueued (default every 30 minutes).",
    )
    fantasy_turns_horizon_days: int = Field(
        default=14,
        validation_alias="FANTASY_TURNS_HORIZON_DAYS",
        ge=1,
        le=60,
        description="How far ahead to materialize weekend/midweek turns.",
    )
    # "Aggiorna calendario" automatico (numerazione turni EP-turni-numerazione):
    # oltre al pulsante admin on-demand, un giro periodico più raro copre
    # l'intera stagione — così le fixture "da aggiornare" che ricevono una
    # data lontana dall'orizzonte di ensure_upcoming entrano comunque in un
    # turno senza bisogno che l'admin prema il pulsante.
    fantasy_turns_full_refresh_enabled: bool = Field(
        default=True,
        validation_alias="FANTASY_TURNS_FULL_REFRESH_ENABLED",
        description=(
            "When true, Celery beat periodically runs the full-season calendar "
            "refresh (provider sync + backfill + renumbering) for active leagues."
        ),
    )
    fantasy_turns_full_refresh_interval_seconds: int = Field(
        default=21_600,
        validation_alias="FANTASY_TURNS_FULL_REFRESH_INTERVAL_SECONDS",
        ge=3600,
        le=604_800,
        description="How often the full-season calendar refresh is enqueued (default every 6h).",
    )

    @field_validator(
        "fantasy_turns_auto_generate_enabled",
        "fantasy_turns_full_refresh_enabled",
        "ai_lineups_auto_generate_enabled",
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
