"""Profile field validation rules (EP02-02)."""

from __future__ import annotations

import base64
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from profiles.errors import InvalidAvatarError, ProfileValidationError

ALLOWED_LANGUAGES = frozenset({"it", "en", "es", "fr", "de"})
_DISPLAY_NAME_PATTERN = re.compile(r"^[\w\s\-'.]{1,80}$", re.UNICODE)
_AVATAR_MIME_PREFIXES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",
}


class ProfileValidationRuleError(ValueError):
    """Raised when profile input fails a domain validation rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_display_name(display_name: str) -> str:
    trimmed = display_name.strip()
    if not trimmed:
        raise ProfileValidationRuleError("display_name_empty", "Display name cannot be empty.")
    if len(trimmed) > 80:
        raise ProfileValidationRuleError(
            "display_name_too_long",
            "Display name must be at most 80 characters.",
        )
    if not _DISPLAY_NAME_PATTERN.fullmatch(trimmed):
        raise ProfileValidationRuleError(
            "display_name_invalid",
            "Display name contains unsupported characters.",
        )
    return trimmed


def validate_language(language: str) -> str:
    normalized = language.strip().lower()
    if normalized not in ALLOWED_LANGUAGES:
        raise ProfileValidationRuleError(
            "language_not_supported",
            f"Language '{language}' is not supported.",
        )
    return normalized


def validate_timezone(timezone: str) -> str:
    candidate = timezone.strip()
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ProfileValidationRuleError(
            "timezone_invalid",
            f"Timezone '{timezone}' is not valid.",
        ) from exc
    return candidate


def validate_avatar_bytes(*, content: bytes, content_type: str | None, max_bytes: int) -> str:
    """Validate uploaded avatar bytes and return a data URL."""

    if not content:
        raise InvalidAvatarError("Avatar file is empty.")
    if len(content) > max_bytes:
        raise InvalidAvatarError(f"Avatar must be at most {max_bytes // 1024} KB.")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in _AVATAR_MIME_PREFIXES:
        raise InvalidAvatarError("Avatar must be JPEG, PNG, or WebP.")

    prefix = _AVATAR_MIME_PREFIXES[mime]
    if mime == "image/webp":
        if len(content) < 12 or content[:4] != prefix or content[8:12] != b"WEBP":
            raise InvalidAvatarError("Avatar file content does not match its type.")
    elif not content.startswith(prefix):
        raise InvalidAvatarError("Avatar file content does not match its type.")

    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def rule_error_to_profile_error(exc: ProfileValidationRuleError) -> ProfileValidationError:
    return ProfileValidationError(exc.message)
