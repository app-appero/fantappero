"""Unit tests for league configuration validation (EP03-01)."""

from __future__ import annotations

import uuid

import pytest

from leagues.validation import (
    LeagueValidationRuleError,
    validate_competition_ids,
    validate_league_name,
    validate_season_year,
)


def test_validate_league_name_trims_and_accepts() -> None:
    assert validate_league_name("  My League  ") == "My League"


def test_validate_league_name_rejects_empty() -> None:
    with pytest.raises(LeagueValidationRuleError) as exc:
        validate_league_name("   ")
    assert exc.value.code == "league_name_empty"


def test_validate_league_name_rejects_too_long() -> None:
    with pytest.raises(LeagueValidationRuleError) as exc:
        validate_league_name("x" * 121)
    assert exc.value.code == "league_name_too_long"


def test_validate_season_year_accepts_current_window() -> None:
    assert validate_season_year(2025) == 2025


def test_validate_season_year_rejects_past() -> None:
    with pytest.raises(LeagueValidationRuleError) as exc:
        validate_season_year(2019)
    assert exc.value.code == "season_year_out_of_range"


def test_validate_competition_ids_requires_minimum() -> None:
    allowed = {uuid.uuid4(), uuid.uuid4()}
    with pytest.raises(LeagueValidationRuleError) as exc:
        validate_competition_ids([next(iter(allowed))], allowed_ids=allowed)
    assert exc.value.code == "competition_ids_too_few"


def test_validate_competition_ids_rejects_duplicates() -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()
    third = uuid.uuid4()
    with pytest.raises(LeagueValidationRuleError) as exc:
        validate_competition_ids([first, second, first], allowed_ids={first, second, third})
    assert exc.value.code == "competition_ids_duplicate"


def test_validate_competition_ids_rejects_unknown() -> None:
    known = {uuid.uuid4() for _ in range(3)}
    unknown = uuid.uuid4()
    with pytest.raises(LeagueValidationRuleError) as exc:
        validate_competition_ids([*known, unknown], allowed_ids=known)
    assert exc.value.code == "competition_ids_invalid"


def test_validate_competition_ids_accepts_three_or_more() -> None:
    ids = [uuid.uuid4() for _ in range(3)]
    assert validate_competition_ids(ids, allowed_ids=set(ids)) == ids
