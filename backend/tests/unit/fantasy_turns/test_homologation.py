"""Unit tests for the provisional/homologated guard (EP07-07 / FR-OMO-01)."""

from __future__ import annotations

import pytest

import database.models  # noqa: F401  (registers all ORM relationship targets)
from auth.exceptions import ValidationAuthError
from database.enums import FantasyRoundHomologationStatus
from fantasy_turns.homologation import assert_round_not_homologated, is_homologated
from fantasy_turns.models import FantasyRound


def _round(status: FantasyRoundHomologationStatus) -> FantasyRound:
    return FantasyRound(homologation_status=status)


def test_is_homologated() -> None:
    assert is_homologated(_round(FantasyRoundHomologationStatus.HOMOLOGATED)) is True
    assert is_homologated(_round(FantasyRoundHomologationStatus.PROVISIONAL)) is False


def test_assert_round_not_homologated_allows_provisional() -> None:
    assert_round_not_homologated(_round(FantasyRoundHomologationStatus.PROVISIONAL))


def test_assert_round_not_homologated_blocks_homologated() -> None:
    with pytest.raises(ValidationAuthError) as excinfo:
        assert_round_not_homologated(_round(FantasyRoundHomologationStatus.HOMOLOGATED))
    assert excinfo.value.code == "round_homologated"
