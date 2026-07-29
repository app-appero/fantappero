"""Unit tests for profile validation rules."""

from __future__ import annotations

import pytest

from profiles.errors import InvalidAvatarError
from profiles.validation import (
    ProfileValidationRuleError,
    validate_avatar_bytes,
    validate_display_name,
    validate_language,
    validate_timezone,
)

_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_validate_display_name_trims() -> None:
    assert validate_display_name("  Mario Rossi  ") == "Mario Rossi"


def test_validate_display_name_rejects_empty() -> None:
    with pytest.raises(ProfileValidationRuleError) as exc:
        validate_display_name("   ")
    assert exc.value.code == "display_name_empty"


def test_validate_language_accepts_supported() -> None:
    assert validate_language("IT") == "it"


def test_validate_language_rejects_unknown() -> None:
    with pytest.raises(ProfileValidationRuleError) as exc:
        validate_language("xx")
    assert exc.value.code == "language_not_supported"


def test_validate_timezone_accepts_iana() -> None:
    assert validate_timezone("Europe/Rome") == "Europe/Rome"


def test_validate_timezone_rejects_invalid() -> None:
    with pytest.raises(ProfileValidationRuleError) as exc:
        validate_timezone("Not/AZone")
    assert exc.value.code == "timezone_invalid"


def test_validate_avatar_bytes_accepts_png() -> None:
    data_url = validate_avatar_bytes(
        content=_MIN_PNG,
        content_type="image/png",
        max_bytes=1024 * 1024,
    )
    assert data_url.startswith("data:image/png;base64,")


def test_validate_avatar_bytes_rejects_oversized() -> None:
    with pytest.raises(InvalidAvatarError):
        validate_avatar_bytes(content=_MIN_PNG, content_type="image/png", max_bytes=10)


def test_validate_avatar_bytes_rejects_wrong_mime() -> None:
    with pytest.raises(InvalidAvatarError):
        validate_avatar_bytes(content=_MIN_PNG, content_type="image/gif", max_bytes=1024)
