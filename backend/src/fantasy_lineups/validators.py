"""Request validators for lineup save (EP06-02)."""

from __future__ import annotations

from uuid import UUID

from auth.exceptions import ValidationAuthError
from fantasy_lineups.rules import parse_module


def validate_athlete_id_list(values: list[UUID]) -> list[UUID]:
    if any(item is None for item in values):
        raise ValidationAuthError(
            "Ogni slot della formazione deve contenere un calciatore.",
            code="missing_athlete",
        )
    return values


def validate_module_code(value: str) -> str:
    if parse_module(value) is None:
        raise ValidationAuthError(
            "Modulo non ammesso. Scegli uno dei sette moduli validi.",
            code="invalid_module",
        )
    return value


def parse_optional_athlete_ids(values: list[str]) -> list[str]:
    parsed: list[str] = []
    for raw in values:
        value = (raw or "").strip()
        if not value:
            parsed.append("")
            continue
        try:
            parsed.append(str(UUID(value)))
        except ValueError as exc:
            raise ValidationAuthError(
                "Identificativo calciatore non valido.",
                code="invalid_athlete_id",
            ) from exc
    return parsed
