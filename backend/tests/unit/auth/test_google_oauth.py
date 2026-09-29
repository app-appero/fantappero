"""Google ID token verification (no network — JWKS lookup is stubbed)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from auth import google_oauth
from auth.exceptions import GoogleAuthError

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class _FakeJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        del token
        return _FakeSigningKey(_PRIVATE_KEY.public_key())


@pytest.fixture(autouse=True)
def _fake_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_oauth, "_get_jwks_client", lambda: _FakeJwksClient())


def _make_token(**overrides: object) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": "test-client-id",
        "sub": "1234567890",
        "email": "user@example.com",
        "email_verified": True,
        "name": "Test User",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    payload.update(overrides)
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")


def test_verify_id_token_accepts_valid_token() -> None:
    identity = google_oauth.verify_id_token(_make_token(), allowed_audiences=["test-client-id"])
    assert identity.sub == "1234567890"
    assert identity.email == "user@example.com"
    assert identity.email_verified is True
    assert identity.name == "Test User"


def test_verify_id_token_normalizes_email_case() -> None:
    identity = google_oauth.verify_id_token(
        _make_token(email="User@Example.com"),
        allowed_audiences=["test-client-id"],
    )
    assert identity.email == "user@example.com"


def test_verify_id_token_rejects_wrong_audience() -> None:
    with pytest.raises(GoogleAuthError):
        google_oauth.verify_id_token(_make_token(), allowed_audiences=["other-client-id"])


def test_verify_id_token_rejects_empty_allowed_audiences() -> None:
    with pytest.raises(GoogleAuthError):
        google_oauth.verify_id_token(_make_token(), allowed_audiences=[])


def test_verify_id_token_rejects_wrong_issuer() -> None:
    token = _make_token(iss="https://evil.example.com")
    with pytest.raises(GoogleAuthError):
        google_oauth.verify_id_token(token, allowed_audiences=["test-client-id"])


def test_verify_id_token_rejects_expired_token() -> None:
    now = datetime.now(UTC)
    token = _make_token(iat=now - timedelta(hours=2), exp=now - timedelta(hours=1))
    with pytest.raises(GoogleAuthError):
        google_oauth.verify_id_token(token, allowed_audiences=["test-client-id"])
