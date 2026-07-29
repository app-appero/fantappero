"""Authentication dependencies for FastAPI routes."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.deps_db import get_db
from auth.errors import AuthError, InvalidSessionError
from auth.rate_limit import RateLimiter, create_rate_limiter
from auth.service import AuthService
from config.settings.api import ApiSettings
from config.settings.auth import AuthSettings
from database.models.accounts import AuthSession, User

_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings()


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return create_rate_limiter(ApiSettings().redis_url)


def reset_auth_deps_cache() -> None:
    get_auth_settings.cache_clear()
    if hasattr(get_rate_limiter, "cache_clear"):
        get_rate_limiter.cache_clear()


def get_auth_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AuthService:
    return AuthService(db, settings, rate_limiter)


def client_rate_limit_key(request: Request, email: str | None = None) -> str:
    host = request.client.host if request.client else "unknown"
    if email:
        return f"{host}:{email.lower()}"
    return host


def _extract_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    authorization: str | None = Header(default=None),
) -> str | None:
    if credentials is not None:
        return credentials.credentials
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_optional_user(
    raw_token: Annotated[str | None, Depends(_extract_bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> User | None:
    if not raw_token:
        return None
    try:
        user, _ = service.get_user_from_session(raw_token)
    except InvalidSessionError:
        return None
    return user


def get_current_user(
    raw_token: Annotated[str | None, Depends(_extract_bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    if not raw_token:
        raise InvalidSessionError()
    user, _ = service.get_user_from_session(raw_token)
    return user


def get_current_session(
    raw_token: Annotated[str | None, Depends(_extract_bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSession:
    if not raw_token:
        raise InvalidSessionError()
    _, session = service.get_user_from_session(raw_token)
    return session


def auth_error_to_http(exc: AuthError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}
