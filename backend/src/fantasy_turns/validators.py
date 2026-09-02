"""Validators for european fantasy turn requests (EP06-01)."""

from __future__ import annotations

from datetime import date

from auth.exceptions import ValidationAuthError
from database.enums import FantasyTurnKind
from fantasy_turns.rules import (
    MAX_FIXTURES_PER_ROUND,
    MIN_FIXTURES_PER_ROUND,
)


def validate_turn_kind(raw: str) -> FantasyTurnKind:
    try:
        return FantasyTurnKind(raw)
    except ValueError as exc:
        raise ValidationAuthError(
            "Tipo di turno non supportato.",
            code="invalid_turn_kind",
        ) from exc


def validate_anchor_date(value: date) -> date:
    if value.year < 2020 or value.year > 2100:
        raise ValidationAuthError(
            "Data di riferimento del turno non valida.",
            code="invalid_anchor_date",
        )
    return value


def validate_min_fixtures_per_round(value: int) -> int:
    if value < MIN_FIXTURES_PER_ROUND or value > MAX_FIXTURES_PER_ROUND:
        raise ValidationAuthError(
            f"La soglia partite deve essere tra {MIN_FIXTURES_PER_ROUND} e "
            f"{MAX_FIXTURES_PER_ROUND}.",
            code="invalid_min_fixtures_per_round",
        )
    return value


#: Estremi della soglia di copertura formazione (EP-turni-copertura).
MIN_TURN_COVERAGE_THRESHOLD = 0.50
MAX_TURN_COVERAGE_THRESHOLD = 1.00


def validate_turn_coverage_threshold(value: float) -> float:
    if value < MIN_TURN_COVERAGE_THRESHOLD or value > MAX_TURN_COVERAGE_THRESHOLD:
        raise ValidationAuthError(
            "La copertura formazione richiesta deve essere tra "
            f"{int(MIN_TURN_COVERAGE_THRESHOLD * 100)}% e "
            f"{int(MAX_TURN_COVERAGE_THRESHOLD * 100)}%.",
            code="invalid_turn_coverage_threshold",
        )
    return round(value, 2)
