"""Validation unit tests."""

from __future__ import annotations

import pytest

from auth.exceptions import ValidationAuthError
from auth.validators import validate_display_name, validate_email, validate_password


def test_validate_email_normalizes() -> None:
    assert validate_email("  User@Example.COM ") == "user@example.com"


def test_validate_email_rejects_invalid() -> None:
    with pytest.raises(ValidationAuthError):
        validate_email("not-an-email")


def test_validate_password_min_length() -> None:
    with pytest.raises(ValidationAuthError):
        validate_password("short")
    assert validate_password("longenough") == "longenough"


def test_validate_display_name_required() -> None:
    with pytest.raises(ValidationAuthError):
        validate_display_name("   ")
    assert validate_display_name("  Marco  ") == "Marco"
