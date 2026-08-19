"""Validation rules for account export and deletion (EP02-04)."""

from __future__ import annotations

from uuid import UUID

from auth.exceptions import InvalidCredentialsError, ValidationAuthError

DELETE_CONFIRMATION_PHRASE = "ELIMINA"
ANONYMIZED_EMAIL_DOMAIN = "anon.fantappero.invalid"


def validate_delete_confirmation(confirm_phrase: str) -> str:
    """Require explicit confirmation phrase before account deletion."""
    normalized = confirm_phrase.strip()
    if normalized != DELETE_CONFIRMATION_PHRASE:
        raise ValidationAuthError(
            f'Digita "{DELETE_CONFIRMATION_PHRASE}" per confermare l\'eliminazione.',
            code="invalid_delete_confirmation",
        )
    return normalized


def build_anonymized_email(user_id: UUID) -> str:
    """Return a unique placeholder email that removes personal identifiers."""
    return f"deleted+{user_id}@{ANONYMIZED_EMAIL_DOMAIN}"


def resolve_historical_display_name(*, profile_name: str | None, email: str) -> str:
    """Pick the label preserved on competitive records after anonymization."""
    if profile_name and profile_name.strip():
        return profile_name.strip()[:80]
    local_part = email.split("@", maxsplit=1)[0]
    return (local_part or email)[:80]


def require_matching_password(*, password_valid: bool) -> None:
    if not password_valid:
        raise InvalidCredentialsError()
