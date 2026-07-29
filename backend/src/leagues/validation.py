"""League configuration validation rules (EP03-01)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from leagues.catalog import MAX_LEAGUE_COMPETITIONS, MIN_LEAGUE_COMPETITIONS
from leagues.errors import LeagueValidationError

MIN_SEASON_YEAR = 2020
MAX_SEASON_YEAR_OFFSET = 2


class LeagueValidationRuleError(ValueError):
    """Raised when league input fails a domain validation rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_league_name(name: str) -> str:
    trimmed = name.strip()
    if not trimmed:
        raise LeagueValidationRuleError("league_name_empty", "League name cannot be empty.")
    if len(trimmed) > 120:
        raise LeagueValidationRuleError(
            "league_name_too_long",
            "League name must be at most 120 characters.",
        )
    return trimmed


def validate_season_year(season_year: int) -> int:
    max_year = datetime.now(UTC).year + MAX_SEASON_YEAR_OFFSET
    if season_year < MIN_SEASON_YEAR or season_year > max_year:
        raise LeagueValidationRuleError(
            "season_year_out_of_range",
            f"Season year must be between {MIN_SEASON_YEAR} and {max_year}.",
        )
    return season_year


def validate_competition_ids(
    competition_ids: list[uuid.UUID],
    *,
    allowed_ids: set[uuid.UUID],
) -> list[uuid.UUID]:
    if len(competition_ids) != len(set(competition_ids)):
        raise LeagueValidationRuleError(
            "competition_ids_duplicate",
            "Each competition may only be selected once.",
        )
    if len(competition_ids) < MIN_LEAGUE_COMPETITIONS:
        raise LeagueValidationRuleError(
            "competition_ids_too_few",
            f"Select at least {MIN_LEAGUE_COMPETITIONS} competitions.",
        )
    if len(competition_ids) > MAX_LEAGUE_COMPETITIONS:
        raise LeagueValidationRuleError(
            "competition_ids_too_many",
            f"Select at most {MAX_LEAGUE_COMPETITIONS} competitions.",
        )

    unknown = [item for item in competition_ids if item not in allowed_ids]
    if unknown:
        raise LeagueValidationRuleError(
            "competition_ids_invalid",
            "One or more competitions are not available.",
        )
    return list(competition_ids)


def rule_error_to_league_error(exc: LeagueValidationRuleError) -> LeagueValidationError:
    return LeagueValidationError(exc.message)
