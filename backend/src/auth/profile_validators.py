"""Validation rules for profile preferences and avatar uploads (EP02-02)."""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo, available_timezones

from auth.exceptions import ValidationAuthError

_DISPLAY_NAME_MAX_LENGTH = 80
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
_SUPPORTED_LANGUAGES = frozenset({"it"})

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF = b"RIFF"
_WEBP_MARKER = b"WEBP"


def validate_profile_display_name(display_name: str) -> str:
    cleaned = display_name.strip()
    if not cleaned:
        raise ValidationAuthError("Inserisci un nome visualizzato.", code="invalid_display_name")
    if len(cleaned) > _DISPLAY_NAME_MAX_LENGTH:
        raise ValidationAuthError(
            "Il nome visualizzato è troppo lungo.",
            code="invalid_display_name",
        )
    return cleaned


def validate_language(language: str) -> str:
    normalized = language.strip()
    if not _LANGUAGE_PATTERN.match(normalized):
        raise ValidationAuthError("Seleziona una lingua valida.", code="invalid_language")
    if normalized not in _SUPPORTED_LANGUAGES:
        raise ValidationAuthError(
            "La lingua selezionata non è ancora disponibile.",
            code="unsupported_language",
        )
    return normalized


def validate_timezone(timezone: str) -> str:
    candidate = timezone.strip()
    if candidate not in available_timezones():
        raise ValidationAuthError("Seleziona un fuso orario valido.", code="invalid_timezone")
    try:
        ZoneInfo(candidate)
    except Exception as exc:
        raise ValidationAuthError(
            "Seleziona un fuso orario valido.",
            code="invalid_timezone",
        ) from exc
    return candidate


def validate_policy_version(policy_version: str, expected_version: str) -> str:
    normalized = policy_version.strip()
    if normalized != expected_version:
        raise ValidationAuthError(
            "La versione della policy non è aggiornata. Ricarica la pagina e riprova.",
            code="invalid_policy_version",
        )
    return normalized


def detect_avatar_content_type(data: bytes) -> str | None:
    if len(data) >= 3 and data[:3] == _JPEG_MAGIC:
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == _PNG_MAGIC:
        return "image/png"
    if len(data) >= 12 and data[:4] == _WEBP_RIFF and data[8:12] == _WEBP_MARKER:
        return "image/webp"
    return None


def validate_avatar_upload(*, data: bytes, max_bytes: int) -> tuple[str, str]:
    if not data:
        raise ValidationAuthError("Seleziona un'immagine da caricare.", code="invalid_avatar")
    if len(data) > max_bytes:
        raise ValidationAuthError(
            "L'immagine supera la dimensione massima consentita (2 MB).",
            code="avatar_too_large",
        )
    content_type = detect_avatar_content_type(data)
    if content_type is None:
        raise ValidationAuthError(
            "Formato non supportato. Usa JPEG, PNG o WebP.",
            code="invalid_avatar_format",
        )
    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[content_type]
    return content_type, extension
