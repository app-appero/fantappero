"""Security helper unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from auth.security import (
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    hashed = hash_password("password-segreta")
    assert verify_password(hashed, "password-segreta")
    assert not verify_password(hashed, "altra-password")


def test_verify_password_rejects_invalid_hash() -> None:
    assert not verify_password("not-an-argon2-hash", "password-segreta")


def test_opaque_token_hash_is_stable() -> None:
    token = "abc123"
    assert hash_opaque_token(token) == hash_opaque_token(token)
    assert hash_opaque_token(token) != hash_opaque_token("other")


def test_generate_opaque_token_unique() -> None:
    assert generate_opaque_token() != generate_opaque_token()


def test_access_token_roundtrip() -> None:
    user_id = uuid4()
    secret = "unit-test-secret"
    token, expires_in = create_access_token(user_id=user_id, secret=secret, expire_minutes=15)
    assert expires_in == 15 * 60
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_access_token_rejects_wrong_type() -> None:
    secret = "unit-test-secret"
    payload = {
        "sub": str(uuid4()),
        "type": "refresh",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        from auth.security import decode_access_token

        decode_access_token(token, secret=secret)
