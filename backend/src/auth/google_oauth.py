"""Google Sign-In ID token verification."""

from __future__ import annotations

from dataclasses import dataclass

import jwt

from auth.exceptions import GoogleAuthError

_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(_GOOGLE_JWKS_URL)
    return _jwks_client


@dataclass(frozen=True)
class GoogleIdentity:
    """Claims extracted from a verified Google ID token."""

    sub: str
    email: str
    email_verified: bool
    name: str | None


def verify_id_token(id_token: str, *, allowed_audiences: list[str]) -> GoogleIdentity:
    """Verify a Google-issued ID token and return its identity claims.

    Raises ``GoogleAuthError`` for any signature, issuer, audience, or
    expiry failure so callers never have to distinguish JWT-library
    exceptions from domain errors.
    """
    if not allowed_audiences:
        raise GoogleAuthError()
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=allowed_audiences,
            issuer=list(_GOOGLE_ISSUERS),
        )
    except jwt.PyJWTError as exc:
        raise GoogleAuthError() from exc

    email = payload.get("email")
    sub = payload.get("sub")
    if not email or not sub:
        raise GoogleAuthError()

    return GoogleIdentity(
        sub=str(sub),
        email=str(email).strip().lower(),
        email_verified=bool(payload.get("email_verified", False)),
        name=payload.get("name"),
    )
