"""Input validation for auth flows."""

from __future__ import annotations

import re

from auth.exceptions import ValidationAuthError

_PASSWORD_MIN_LENGTH = 8
_DISPLAY_NAME_MAX_LENGTH = 120
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or not _EMAIL_PATTERN.match(normalized):
        raise ValidationAuthError("Inserisci un indirizzo email valido.", code="invalid_email")
    if len(normalized) > 320:
        raise ValidationAuthError("L'indirizzo email è troppo lungo.", code="invalid_email")
    return normalized


def validate_password(password: str) -> str:
    if len(password) < _PASSWORD_MIN_LENGTH:
        raise ValidationAuthError(
            f"La password deve contenere almeno {_PASSWORD_MIN_LENGTH} caratteri.",
            code="invalid_password",
        )
    if len(password) > 128:
        raise ValidationAuthError("La password è troppo lunga.", code="invalid_password")
    return password


def validate_display_name(display_name: str) -> str:
    cleaned = display_name.strip()
    if not cleaned:
        raise ValidationAuthError("Inserisci un nome visualizzato.", code="invalid_display_name")
    if len(cleaned) > _DISPLAY_NAME_MAX_LENGTH:
        raise ValidationAuthError(
            "Il nome visualizzato è troppo lungo.",
            code="invalid_display_name",
        )
    return cleaned
