"""Unit tests for listone override timing rules (EP04-04)."""

from __future__ import annotations

import pytest

from database.enums import FantasyRole, LeagueState
from sports_data.listone.validators import (
    ListoneValidationError,
    compute_override_effective_from_round,
    is_override_effective,
    resolve_effective_role,
    validate_fantasy_role,
)


@pytest.mark.parametrize(
    "state",
    [LeagueState.DRAFT, LeagueState.CONFIGURING, LeagueState.AUCTION],
)
def test_pre_auction_override_is_immediate(state: LeagueState) -> None:
    assert compute_override_effective_from_round(league_state=state, current_round=3) is None


def test_active_override_defers_to_next_round() -> None:
    assert (
        compute_override_effective_from_round(
            league_state=LeagueState.ACTIVE,
            current_round=2,
        )
        == 3
    )


def test_active_override_defaults_current_round_zero() -> None:
    assert (
        compute_override_effective_from_round(
            league_state=LeagueState.ACTIVE,
            current_round=None,
        )
        == 1
    )


@pytest.mark.parametrize("state", [LeagueState.CONCLUDED, LeagueState.ARCHIVED])
def test_locked_states_reject_override(state: LeagueState) -> None:
    with pytest.raises(ListoneValidationError) as exc:
        compute_override_effective_from_round(league_state=state, current_round=1)
    assert exc.value.code == "league_role_override_locked"


def test_resolve_effective_role_pending_keeps_official() -> None:
    role = resolve_effective_role(
        official_role=FantasyRole.C,
        override_role=FantasyRole.A,
        override_effective_from_round=4,
        current_round=3,
    )
    assert role == FantasyRole.C


def test_resolve_effective_role_applies_from_round() -> None:
    role = resolve_effective_role(
        official_role=FantasyRole.C,
        override_role=FantasyRole.A,
        override_effective_from_round=4,
        current_round=4,
    )
    assert role == FantasyRole.A


def test_immediate_override_always_effective() -> None:
    assert is_override_effective(effective_from_round=None, current_round=0) is True


def test_validate_fantasy_role() -> None:
    assert validate_fantasy_role("d") == FantasyRole.D
    with pytest.raises(ListoneValidationError) as exc:
        validate_fantasy_role("WB")
    assert exc.value.code == "invalid_fantasy_role"
