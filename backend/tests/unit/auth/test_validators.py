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


def test_validate_password_rejects_common_passwords() -> None:
    """Decisione 12 (18/11): le password più comuni non sono ammesse."""
    from auth.validators import common_passwords

    assert len(common_passwords()) == 10_000
    for weak in ("password", "12345678", "Password1", "QWERTYUIOP"):
        with pytest.raises(ValidationAuthError) as exc:
            validate_password(weak)
        assert exc.value.code == "password_too_common"
    assert validate_password("Password123!") == "Password123!"


def test_validate_password_rejects_the_email_itself() -> None:
    with pytest.raises(ValidationAuthError) as exc:
        validate_password("Mario.Rossi@Example.com", email="mario.rossi@example.com")
    assert exc.value.code == "password_same_as_email"
    assert validate_password("Password123!", email="mario.rossi@example.com")
