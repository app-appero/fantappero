"""Profile validation unit tests (EP02-02)."""

from __future__ import annotations

import pytest

from auth.exceptions import ValidationAuthError
from auth.profile_validators import (
    detect_avatar_content_type,
    validate_avatar_upload,
    validate_language,
    validate_policy_version,
    validate_profile_display_name,
    validate_timezone,
)

_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_validate_profile_display_name_trims() -> None:
    assert validate_profile_display_name("  Marco  ") == "Marco"


def test_validate_profile_display_name_rejects_empty() -> None:
    with pytest.raises(ValidationAuthError, match="nome visualizzato"):
        validate_profile_display_name("   ")


def test_validate_language_accepts_italian() -> None:
    assert validate_language("it") == "it"


def test_validate_language_rejects_unsupported() -> None:
    with pytest.raises(ValidationAuthError, match="non è ancora disponibile"):
        validate_language("en")


def test_validate_timezone_accepts_rome() -> None:
    assert validate_timezone("Europe/Rome") == "Europe/Rome"


def test_validate_timezone_rejects_invalid() -> None:
    with pytest.raises(ValidationAuthError, match="fuso orario"):
        validate_timezone("Not/AZone")


def test_validate_policy_version_matches_expected() -> None:
    assert validate_policy_version("2026-01", "2026-01") == "2026-01"


def test_validate_policy_version_rejects_stale() -> None:
    with pytest.raises(ValidationAuthError, match="policy"):
        validate_policy_version("2025-01", "2026-01")


def test_validate_avatar_upload_accepts_png() -> None:
    content_type, extension = validate_avatar_upload(data=_MINIMAL_PNG, max_bytes=1024 * 1024)
    assert content_type == "image/png"
    assert extension == "png"


def test_validate_avatar_upload_rejects_empty() -> None:
    with pytest.raises(ValidationAuthError, match="Seleziona"):
        validate_avatar_upload(data=b"", max_bytes=1024)


def test_validate_avatar_upload_rejects_oversized() -> None:
    with pytest.raises(ValidationAuthError, match="dimensione"):
        validate_avatar_upload(data=_MINIMAL_PNG, max_bytes=10)


def test_detect_avatar_content_type_rejects_unknown() -> None:
    assert detect_avatar_content_type(b"not-an-image") is None
