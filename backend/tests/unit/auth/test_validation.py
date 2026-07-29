"""Unit tests for auth validation rules."""

from __future__ import annotations

import pytest

from auth.validation import ValidationRuleError, normalize_email, validate_password


def test_normalize_email_lowercases() -> None:
    assert normalize_email("Player@Example.COM") == "player@example.com"


def test_normalize_email_rejects_invalid() -> None:
    with pytest.raises(ValidationRuleError) as exc:
        normalize_email("not-an-email")
    assert exc.value.code == "invalid_email"


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("short1", "password_too_short"),
        ("12345678", "password_missing_letter"),
        ("abcdefgh", "password_missing_digit"),
    ],
)
def test_validate_password_rules(password: str, code: str) -> None:
    with pytest.raises(ValidationRuleError) as exc:
        validate_password(password)
    assert exc.value.code == code


def test_validate_password_accepts_strong_password() -> None:
    validate_password("Secret123")
