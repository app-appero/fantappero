"""Password hashing, JWT, and opaque token helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_password_hasher = PasswordHasher()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: UUID,
    secret: str,
    expire_minutes: int,
) -> tuple[str, int]:
    expires_in = expire_minutes * 60
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(seconds=expires_in),
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, expires_in


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        msg = "invalid token type"
        raise jwt.InvalidTokenError(msg)
    return payload


def utc_now() -> datetime:
    return datetime.now(UTC)
