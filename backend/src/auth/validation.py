"""Registration and credential validation rules."""

from __future__ import annotations

import re

from pydantic import EmailStr, TypeAdapter, ValidationError

_EMAIL_ADAPTER = TypeAdapter(EmailStr)
_PASSWORD_HAS_LETTER = re.compile(r"[A-Za-z]")
_PASSWORD_HAS_DIGIT = re.compile(r"\d")


class ValidationRuleError(ValueError):
    """Raised when user input fails a domain validation rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_email(email: str) -> str:
    """Validate and normalize email to lowercase."""

    try:
        validated = _EMAIL_ADAPTER.validate_python(email.strip())
    except ValidationError as exc:
        raise ValidationRuleError("invalid_email", "Email address is not valid.") from exc
    return str(validated).lower()


def validate_password(password: str) -> None:
    """Enforce minimum password complexity."""

    if len(password) < 8:
        raise ValidationRuleError(
            "password_too_short",
            "Password must be at least 8 characters.",
        )
    if not _PASSWORD_HAS_LETTER.search(password):
        raise ValidationRuleError(
            "password_missing_letter",
            "Password must contain at least one letter.",
        )
    if not _PASSWORD_HAS_DIGIT.search(password):
        raise ValidationRuleError(
            "password_missing_digit",
            "Password must contain at least one digit.",
        )
