"""Riconoscimento dei file allegati e link firmati per vederli."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from uuid import UUID

# content type -> (tipo, estensione)
_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
}


def detect_content_type(data: bytes) -> str | None:
    """Tipo reale dal contenuto (mai dal nome o dal tipo dichiarato dal client)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        return "video/quicktime" if brand == b"qt  " else "video/mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    return None


def kind_of(content_type: str) -> str:
    return "image" if content_type in _IMAGE_TYPES else "video"


def extension_of(content_type: str) -> str:
    return _IMAGE_TYPES.get(content_type) or _VIDEO_TYPES[content_type]


def _sign(secret: str, attachment_id: UUID, expires_at: int) -> str:
    message = f"{attachment_id}:{expires_at}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def make_media_token(
    secret: str, attachment_id: UUID, *, ttl_seconds: int, now: float | None = None
) -> str:
    """Token a scadenza che autorizza la lettura di UN allegato (vedi `verify_media_token`)."""
    expires_at = int((time.time() if now is None else now) + ttl_seconds)
    return f"{expires_at}.{_sign(secret, attachment_id, expires_at)}"


def verify_media_token(
    secret: str,
    attachment_id: UUID,
    token: str,
    *,
    now: float | None = None,
) -> bool:
    expires_raw, _, signature = token.partition(".")
    if not expires_raw.isdigit() or not signature:
        return False
    expires_at = int(expires_raw)
    if expires_at < (time.time() if now is None else now):
        return False
    return hmac.compare_digest(signature, _sign(secret, attachment_id, expires_at))
