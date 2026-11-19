"""Profile validation unit tests (EP02-02)."""

from __future__ import annotations

import pytest

from auth.exceptions import ValidationAuthError
from auth.profile_validators import (
    avatar_size_limit_label,
    detect_avatar_content_type,
    validate_avatar_upload,
    validate_language,
    validate_policy_version,
    validate_profile_display_name,
    validate_profile_nickname,
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


def test_validate_profile_nickname_normalizes_and_allows_empty() -> None:
    assert validate_profile_nickname("  Nick  Name ") == "Nick Name"
    assert validate_profile_nickname("  ") is None


def test_validate_profile_nickname_rejects_invalid_values() -> None:
    with pytest.raises(ValidationAuthError, match="nickname"):
        validate_profile_nickname("x")
    with pytest.raises(ValidationAuthError, match="nickname"):
        validate_profile_nickname("nome!")


@pytest.mark.parametrize(
    "lookalike",
    [
        "q\u043007nick1119",  # «a» cirillica (U+0430) al posto della «a» latina
        "\u0410DMIN",  # «A» cirillica maiuscola (U+0410)
        "\u03bd\u03b9\u03ba\u03bf\u03c2",  # «nikos» in greco
        "nick\u03bf",  # «o» greca (U+03BF) in coda
        "a×b",  # «×»: tra le lettere accentate ma non è una lettera
    ],
)
def test_validate_profile_nickname_rejects_non_latin_lookalikes(lookalike: str) -> None:
    """QA 19/11: un nickname con lettere cirilliche o greche si spacciava per un altro."""
    with pytest.raises(ValidationAuthError) as exc:
        validate_profile_nickname(lookalike)
    assert exc.value.code == "invalid_nickname"
    assert "latine" in exc.value.message


def test_validate_profile_nickname_keeps_accented_latin_letters() -> None:
    assert validate_profile_nickname("Niccolò") == "Niccolò"
    assert validate_profile_nickname("José") == "José"
    assert validate_profile_nickname("Ærø_Øst-ÿ.ß") == "Ærø_Øst-ÿ.ß"
    # Accento scritto come carattere combinante: NFKC lo ricompone in «ò».
    assert validate_profile_nickname("Niccolo\u0300") == "Niccolò"
    # Le lettere a larghezza piena restano ammesse perché NFKC le riporta all'ASCII.
    assert validate_profile_nickname("ＡＤＭＩＮ") == "ADMIN"


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


def test_avatar_size_limit_label_uses_configured_mebibytes() -> None:
    assert avatar_size_limit_label(5 * 1024 * 1024) == "5 MB"
    assert avatar_size_limit_label(10) == "10 byte"


def test_detect_avatar_content_type_rejects_unknown() -> None:
    assert detect_avatar_content_type(b"not-an-image") is None


def _real_image(fmt: str, size: tuple[int, int] = (4, 4)) -> bytes:
    import io

    from PIL import Image

    output = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(output, fmt)
    return output.getvalue()


def test_reencode_avatar_accepts_real_images_and_strips_trailing_data() -> None:
    """Decisione 13 (18/11): l'avatar deve essere un'immagine vera."""
    from auth.profile_validators import reencode_avatar

    for content_type, fmt in (
        ("image/jpeg", "JPEG"),
        ("image/png", "PNG"),
        ("image/webp", "WEBP"),
    ):
        payload = _real_image(fmt) + b"<script>alert(1)</script>"
        cleaned = reencode_avatar(payload, content_type)
        assert b"<script>" not in cleaned
        assert detect_avatar_content_type(cleaned) == content_type
    assert reencode_avatar(_MINIMAL_PNG, "image/png")


def test_reencode_avatar_rejects_fake_images() -> None:
    from auth.profile_validators import reencode_avatar

    fake_jpeg = b"\xff\xd8\xff\xe0" + b"<html><script>alert(1)</script></html>"
    fake_png = b"\x89PNG\r\n\x1a\n" + b"<html>not a picture</html>"
    for data, content_type in ((fake_jpeg, "image/jpeg"), (fake_png, "image/png")):
        with pytest.raises(ValidationAuthError) as exc:
            reencode_avatar(data, content_type)
        assert exc.value.code == "invalid_avatar_format"
    # Firma PNG ma contenuto JPEG: rifiutato.
    with pytest.raises(ValidationAuthError):
        reencode_avatar(_real_image("JPEG"), "image/png")
