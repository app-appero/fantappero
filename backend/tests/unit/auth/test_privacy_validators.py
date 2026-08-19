"""Privacy validation unit tests (EP02-04)."""

from __future__ import annotations

from uuid import UUID

import pytest

from auth.exceptions import InvalidCredentialsError, ValidationAuthError
from auth.privacy_validators import (
    DELETE_CONFIRMATION_PHRASE,
    build_anonymized_email,
    require_matching_password,
    resolve_historical_display_name,
    validate_delete_confirmation,
)


def test_validate_delete_confirmation_accepts_exact_phrase() -> None:
    assert validate_delete_confirmation(DELETE_CONFIRMATION_PHRASE) == DELETE_CONFIRMATION_PHRASE


def test_validate_delete_confirmation_rejects_wrong_phrase() -> None:
    with pytest.raises(ValidationAuthError) as exc_info:
        validate_delete_confirmation("elimina")
    assert exc_info.value.code == "invalid_delete_confirmation"


def test_build_anonymized_email_is_unique_and_non_pii() -> None:
    user_id = UUID("11111111-1111-1111-1111-111111111111")
    email = build_anonymized_email(user_id)
    assert email == "deleted+11111111-1111-1111-1111-111111111111@anon.fantappero.invalid"
    assert "@" in email
    assert "example.com" not in email


def test_resolve_historical_display_name_prefers_profile_name() -> None:
    assert (
        resolve_historical_display_name(profile_name="Luca B.", email="luca@example.com")
        == "Luca B."
    )


def test_resolve_historical_display_name_falls_back_to_email_local_part() -> None:
    assert resolve_historical_display_name(profile_name=None, email="luca@example.com") == "luca"


def test_require_matching_password_raises_on_invalid() -> None:
    with pytest.raises(InvalidCredentialsError):
        require_matching_password(password_valid=False)
