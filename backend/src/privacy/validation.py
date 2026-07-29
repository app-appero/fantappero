"""Validation rules for privacy operations."""

from __future__ import annotations


class ValidationRuleError(Exception):
    """Raised when privacy validation fails."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def validate_delete_confirmation(*, password: str | None, confirm: bool | None) -> None:
    """Deletion requires explicit confirmation and the current password."""

    if not confirm:
        raise ValidationRuleError("You must confirm account deletion.")
    if password is None or not password.strip():
        raise ValidationRuleError("Password is required to delete your account.")
