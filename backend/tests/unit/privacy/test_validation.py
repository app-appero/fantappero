"""Privacy validation unit tests (EP02-04)."""

from __future__ import annotations

import pytest

from privacy.validation import ValidationRuleError, validate_delete_confirmation


def test_delete_requires_confirm_and_password() -> None:
    with pytest.raises(ValidationRuleError, match="confirm"):
        validate_delete_confirmation(password="Secret123", confirm=False)

    with pytest.raises(ValidationRuleError, match="Password"):
        validate_delete_confirmation(password="", confirm=True)

    with pytest.raises(ValidationRuleError, match="Password"):
        validate_delete_confirmation(password=None, confirm=True)


def test_delete_accepts_valid_confirmation() -> None:
    validate_delete_confirmation(password="Secret123", confirm=True)
