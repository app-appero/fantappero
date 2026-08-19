"""Unit tests for roster ownership intervals and turn snapshots (EP05-06)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from auth.exceptions import ValidationAuthError
from fantasy_teams.ownership import (
    OwnershipAssignResult,
    parse_as_of,
    validate_round_number,
)


def test_validate_round_number_accepts_positive() -> None:
    assert validate_round_number(1) == 1
    assert validate_round_number(12) == 12


@pytest.mark.parametrize("round_number", [0, -1, -10])
def test_validate_round_number_rejects_non_positive(round_number: int) -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_round_number(round_number)
    assert exc.value.code == "invalid_round_number"


def test_parse_as_of_defaults_to_now() -> None:
    before = datetime.now(UTC)
    parsed = parse_as_of(None)
    after = datetime.now(UTC)
    assert before <= parsed <= after


def test_parse_as_of_accepts_iso_z() -> None:
    parsed = parse_as_of("2026-08-01T12:00:00Z")
    assert parsed == datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def test_parse_as_of_rejects_invalid() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        parse_as_of("non-una-data")
    assert exc.value.code == "invalid_as_of"


def test_ownership_assign_result_fields() -> None:
    result = OwnershipAssignResult(closed=None, opened=None, updated=None)
    assert result.closed is None
    assert result.opened is None
    assert result.updated is None


def test_as_of_window_semantics() -> None:
    """Document reconstruction predicate used by intervals_as_of."""
    acquired = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    released = acquired + timedelta(days=5)
    at_inside = acquired + timedelta(days=1)
    at_after = released + timedelta(hours=1)

    def owned(at: datetime, *, released_at: datetime | None) -> bool:
        return acquired <= at and (released_at is None or released_at > at)

    assert owned(at_inside, released_at=released)
    assert not owned(at_after, released_at=released)
    assert owned(at_after, released_at=None)
    _ = uuid4()  # keep uuid import intentional for future fixture ids
