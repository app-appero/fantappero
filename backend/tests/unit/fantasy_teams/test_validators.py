"""Unit tests for fantasy team validators (EP05-01)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from auth.exceptions import ValidationAuthError
from fantasy_teams.validators import (
    validate_athlete_not_owned_in_league,
    validate_slot_index,
)


def test_validate_slot_index_accepts_bounds() -> None:
    validate_slot_index(slot_index=0, roster_size=35)
    validate_slot_index(slot_index=34, roster_size=35)


@pytest.mark.parametrize("slot_index", [-1, 35, 100])
def test_validate_slot_index_rejects_out_of_range(slot_index: int) -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_slot_index(slot_index=slot_index, roster_size=35)
    assert exc.value.code == "invalid_slot_index"


def test_validate_athlete_not_owned_allows_same_team() -> None:
    team_id = uuid4()
    validate_athlete_not_owned_in_league(existing_team_id=team_id, target_team_id=team_id)


def test_validate_athlete_not_owned_allows_free_athlete() -> None:
    validate_athlete_not_owned_in_league(existing_team_id=None, target_team_id=uuid4())


def test_validate_athlete_not_owned_rejects_other_team() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_athlete_not_owned_in_league(
            existing_team_id=uuid4(),
            target_team_id=uuid4(),
        )
    assert exc.value.code == "athlete_already_owned"
