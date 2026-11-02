"""Riconoscimento allegati e link firmati delle segnalazioni."""

from __future__ import annotations

from uuid import uuid4

from feedback import media

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 16
GIF = b"GIF89a" + b"0" * 16
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 16
MOV = b"\x00\x00\x00\x14ftypqt  " + b"0" * 16
WEBM = b"\x1a\x45\xdf\xa3" + b"0" * 16


def test_detects_images_and_videos_from_content():
    assert media.detect_content_type(JPEG) == "image/jpeg"
    assert media.detect_content_type(PNG) == "image/png"
    assert media.detect_content_type(WEBP) == "image/webp"
    assert media.detect_content_type(GIF) == "image/gif"
    assert media.detect_content_type(MP4) == "video/mp4"
    assert media.detect_content_type(MOV) == "video/quicktime"
    assert media.detect_content_type(WEBM) == "video/webm"


def test_rejects_other_files_even_with_a_fake_name():
    assert media.detect_content_type(b"MZ\x90\x00 exe pretending to be a png") is None
    assert media.detect_content_type(b"<html><script>alert(1)</script></html>") is None
    assert media.detect_content_type(b"%PDF-1.7 ...") is None
    assert media.detect_content_type(b"") is None


def test_kind_and_extension():
    assert media.kind_of("image/png") == "image"
    assert media.kind_of("video/mp4") == "video"
    assert media.extension_of("video/quicktime") == "mov"
    assert media.extension_of("image/jpeg") == "jpg"


def test_media_token_is_valid_until_it_expires():
    attachment_id = uuid4()
    token = media.make_media_token("secret", attachment_id, ttl_seconds=900, now=1_000.0)
    assert media.verify_media_token("secret", attachment_id, token, now=1_500.0)
    assert not media.verify_media_token("secret", attachment_id, token, now=2_000.0)


def test_media_token_is_bound_to_one_attachment_and_one_secret():
    attachment_id = uuid4()
    token = media.make_media_token("secret", attachment_id, ttl_seconds=900, now=1_000.0)
    assert not media.verify_media_token("secret", uuid4(), token, now=1_100.0)
    assert not media.verify_media_token("other-secret", attachment_id, token, now=1_100.0)


def test_malformed_tokens_are_rejected():
    attachment_id = uuid4()
    for token in ("", "garbage", "123.", ".abc", "abc.def", "9999999999.not-the-signature"):
        assert not media.verify_media_token("secret", attachment_id, token, now=1_000.0)
