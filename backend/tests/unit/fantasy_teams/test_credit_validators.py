"""Unit tests for credit ledger validators (EP05-02)."""

from __future__ import annotations

import pytest

from auth.exceptions import ValidationAuthError
from fantasy_teams.validators import (
    validate_credit_amount_nonzero,
    validate_ledger_balance_non_negative,
    validate_transaction_id,
)


def test_validate_credit_amount_rejects_zero() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_credit_amount_nonzero(0)
    assert exc.value.code == "invalid_credit_amount"


def test_validate_credit_amount_accepts_positive_and_negative() -> None:
    assert validate_credit_amount_nonzero(10) == 10
    assert validate_credit_amount_nonzero(-5) == -5


def test_validate_ledger_balance_rejects_negative() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_ledger_balance_non_negative(-1)
    assert exc.value.code == "insufficient_credits"


def test_validate_ledger_balance_accepts_zero() -> None:
    assert validate_ledger_balance_non_negative(0) == 0


def test_validate_transaction_id_trims_and_rejects_empty() -> None:
    assert validate_transaction_id("  txn-1  ") == "txn-1"
    with pytest.raises(ValidationAuthError) as exc:
        validate_transaction_id("   ")
    assert exc.value.code == "invalid_transaction_id"


def test_validate_transaction_id_rejects_too_long() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_transaction_id("x" * 129)
    assert exc.value.code == "invalid_transaction_id"
