"""Unit tests for market session validators (EP08-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from auth.exceptions import ValidationAuthError
from market.validators import (
    compute_release_refund,
    validate_amount_within_balance,
    validate_athlete_is_free_agent,
    validate_bid_amount,
    validate_session_window,
    validate_slot_has_athlete,
    validate_team_has_free_slot,
)


def test_validate_session_window_rejects_non_positive_duration() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationAuthError) as exc:
        validate_session_window(opens_at=now, closes_at=now)
    assert exc.value.code == "invalid_session_window"
    with pytest.raises(ValidationAuthError):
        validate_session_window(opens_at=now, closes_at=now - timedelta(hours=1))


def test_validate_session_window_accepts_positive_duration() -> None:
    now = datetime.now(UTC)
    validate_session_window(opens_at=now, closes_at=now + timedelta(hours=1))


def test_validate_bid_amount_rejects_non_positive() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_bid_amount(0)
    assert exc.value.code == "invalid_bid_amount"
    with pytest.raises(ValidationAuthError):
        validate_bid_amount(-5)


def test_validate_bid_amount_accepts_positive() -> None:
    assert validate_bid_amount(10) == 10


def test_validate_amount_within_balance_rejects_overdraw() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_amount_within_balance(amount_credits=101, balance=100)
    assert exc.value.code == "insufficient_credits"


def test_validate_amount_within_balance_accepts_equal_balance() -> None:
    validate_amount_within_balance(amount_credits=100, balance=100)


def test_validate_team_has_free_slot_rejects_full_roster() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_team_has_free_slot(has_free_slot=False)
    assert exc.value.code == "roster_full"


def test_validate_athlete_is_free_agent_rejects_owned() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_athlete_is_free_agent(owner_team_id="some-team")
    assert exc.value.code == "athlete_already_owned"


def test_validate_athlete_is_free_agent_accepts_unowned() -> None:
    validate_athlete_is_free_agent(owner_team_id=None)


def test_validate_slot_has_athlete_rejects_empty_slot() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_slot_has_athlete(None)
    assert exc.value.code == "release_slot_empty"


def test_compute_release_refund_uses_floor_rounding() -> None:
    # Documented rounding rule (FR-MKT-02): floor(purchase_credits * percent / 100).
    assert compute_release_refund(purchase_credits=100, refund_percent=50) == 50
    assert compute_release_refund(purchase_credits=99, refund_percent=50) == 49
    assert compute_release_refund(purchase_credits=1, refund_percent=50) == 0
    assert compute_release_refund(purchase_credits=100, refund_percent=100) == 100
    assert compute_release_refund(purchase_credits=100, refund_percent=0) == 0
