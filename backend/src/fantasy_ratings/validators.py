"""Validazioni per il calcolo del voto statistico (EP07-01 / EP07-02)."""

from __future__ import annotations

from uuid import UUID

from fantasy_ratings.eligibility import (
    MAX_MINUTES_THRESHOLD,
    MIN_MINUTES_THRESHOLD,
    coerce_minutes_threshold,
)
from fantasy_ratings.exceptions import FantasyRatingError


def validate_compute_target(
    *,
    fixture_id: UUID | None,
    fixture_provider_id: int | None,
) -> None:
    if fixture_id is None and fixture_provider_id is None:
        raise FantasyRatingError(
            "fixture_target_required",
            "Indica fixtureId oppure fixtureProviderId.",
        )
    if fixture_id is not None and fixture_provider_id is not None:
        raise FantasyRatingError(
            "fixture_target_ambiguous",
            "Indica un solo identificativo fixture.",
        )


def validate_threshold_target(
    *,
    league_id: UUID | None,
    minutes_threshold: int | None,
) -> None:
    if league_id is not None and minutes_threshold is not None:
        raise FantasyRatingError(
            "minutes_threshold_ambiguous",
            "Indica leagueId oppure minutesThreshold, non entrambi.",
        )


def validate_minutes_threshold(value: int) -> int:
    try:
        return coerce_minutes_threshold(value)
    except ValueError as exc:
        raise FantasyRatingError(
            "invalid_minutes_threshold",
            (
                "La soglia minuti deve essere tra "
                f"{MIN_MINUTES_THRESHOLD} e {MAX_MINUTES_THRESHOLD}."
            ),
        ) from exc


def validate_formula_snapshot(formula: dict) -> None:
    required = ("version", "base", "clamp_min", "clamp_max", "roles")
    missing = [key for key in required if key not in formula]
    if missing:
        raise FantasyRatingError(
            "formula_snapshot_invalid",
            "La formula persistita non è ricostruibile.",
        )
