"""Unit tests for minutes threshold and senza voto (EP07-02)."""

from __future__ import annotations

import pytest

from fantasy_ratings.eligibility import (
    MAX_MINUTES_THRESHOLD,
    MIN_MINUTES_THRESHOLD,
    STANDARD_MINUTES_THRESHOLD,
    coerce_minutes_threshold,
    evaluate_eligibility,
    is_second_half_stoppage,
    stoppage_entry_player_ids_from_payload,
)
from fantasy_ratings.exceptions import FantasyRatingError
from fantasy_ratings.validators import validate_minutes_threshold, validate_threshold_target


def test_standard_threshold_is_fifteen() -> None:
    assert STANDARD_MINUTES_THRESHOLD == 15
    assert MIN_MINUTES_THRESHOLD == 1
    assert MAX_MINUTES_THRESHOLD == 30


@pytest.mark.parametrize("value", [1, 15, 30])
def test_coerce_minutes_threshold_accepts_range(value: int) -> None:
    assert coerce_minutes_threshold(value) == value


@pytest.mark.parametrize("value", [0, 31, True])
def test_coerce_minutes_threshold_rejects_invalid(value: int) -> None:
    with pytest.raises(ValueError):
        coerce_minutes_threshold(value)


def test_validate_minutes_threshold_italian_error() -> None:
    with pytest.raises(FantasyRatingError) as error:
        validate_minutes_threshold(0)
    assert error.value.code == "invalid_minutes_threshold"


def test_stoppage_time_detection() -> None:
    assert is_second_half_stoppage(90, 2) is True
    assert is_second_half_stoppage(93, None) is True
    assert is_second_half_stoppage(90, None) is False
    assert is_second_half_stoppage(76, None) is False
    assert is_second_half_stoppage(45, 2) is False


def test_stoppage_entry_ids_from_subst_payload() -> None:
    payload = {
        "response": [
            {
                "type": "subst",
                "player": {"id": 10, "name": "Out"},
                "assist": {"id": 99, "name": "In"},
                "time": {"elapsed": 90, "extra": 3},
            },
            {
                "type": "subst",
                "player": {"id": 11, "name": "Out2"},
                "assist": {"id": 88, "name": "In2"},
                "time": {"elapsed": 76, "extra": None},
            },
        ]
    }
    assert stoppage_entry_player_ids_from_payload(payload) == {99}


def test_stoppage_entry_without_event_is_senza_voto() -> None:
    decision = evaluate_eligibility(
        minutes=2,
        substitute=True,
        role="C",
        has_relevant_event=False,
        entered_in_stoppage=True,
        minutes_threshold=15,
    )
    assert decision.eligible is False
    assert decision.reason == "stoppage_entry_no_relevant_event"


def test_stoppage_entry_with_goal_is_eligible() -> None:
    decision = evaluate_eligibility(
        minutes=1,
        substitute=True,
        role="A",
        has_relevant_event=True,
        entered_in_stoppage=True,
        minutes_threshold=15,
    )
    assert decision.eligible is True
    assert decision.reason == "relevant_event_under_threshold"


def test_configurable_threshold_changes_eligibility() -> None:
    under_20 = evaluate_eligibility(
        minutes=16,
        substitute=True,
        role="C",
        has_relevant_event=False,
        entered_in_stoppage=False,
        minutes_threshold=20,
    )
    at_10 = evaluate_eligibility(
        minutes=16,
        substitute=True,
        role="C",
        has_relevant_event=False,
        entered_in_stoppage=False,
        minutes_threshold=10,
    )
    assert under_20.eligible is False
    assert under_20.reason == "under_threshold_no_relevant_event"
    assert at_10.eligible is True
    assert at_10.reason == "minutes_threshold"


def test_threshold_target_rejects_both() -> None:
    from uuid import uuid4

    with pytest.raises(FantasyRatingError) as error:
        validate_threshold_target(league_id=uuid4(), minutes_threshold=15)
    assert error.value.code == "minutes_threshold_ambiguous"
