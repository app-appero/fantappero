"""FastAPI dependencies for auth."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from auth.exceptions import InvalidCredentialsError
from auth.models.user import User
from auth.privacy_service import PrivacyService
from auth.profile_service import ProfileService
from auth.rate_limit import AuthRateLimiter
from auth.service import AuthService
from config.settings.api import ApiSettings
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory

_bearer = HTTPBearer(auto_error=False)

_engine = None
_session_factory: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_api_settings()
        if not settings.database_url:
            msg = "DATABASE_URL is required for auth"
            raise RuntimeError(msg)
        _engine = create_engine_from_url(settings.database_url)
        _session_factory = create_session_factory(_engine)
    return _session_factory


def reset_db_cache() -> None:
    """Clear cached engine (for tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db_session() -> Generator[Session, None, None]:
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@lru_cache(maxsize=1)
def get_rate_limiter() -> AuthRateLimiter | None:
    settings = get_api_settings()
    if not settings.redis_url:
        return None
    return AuthRateLimiter(settings.redis_url)


def get_auth_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
    rate_limiter: AuthRateLimiter | None = Depends(get_rate_limiter),
) -> AuthService:
    return AuthService(session, settings, rate_limiter)


def get_profile_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> ProfileService:
    return ProfileService(session, settings)


def get_privacy_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> PrivacyService:
    return PrivacyService(session, settings)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidCredentialsError()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.resolved_jwt_secret(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        raise InvalidCredentialsError() from exc
    if payload.get("type") != "access":
        raise InvalidCredentialsError()
    user_id = UUID(str(payload["sub"]))
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise InvalidCredentialsError()
    return user
