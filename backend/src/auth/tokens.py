"""Opaque token generation and hashing for storage."""

from __future__ import annotations

import hashlib
import secrets


def generate_opaque_token() -> str:
    """Return a URL-safe bearer token (returned once to the client)."""

    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex digest for DB lookup without storing raw tokens."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()
