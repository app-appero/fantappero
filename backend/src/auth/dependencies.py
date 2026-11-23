"""FastAPI dependencies for auth."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import BackgroundTasks, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from auth.blocklist import BlockList
from auth.exceptions import AccountBlockedError, SessionRequiredError
from auth.impersonation import ImpersonationStore
from auth.mobile_handoff import MobileHandoffStore
from auth.models.user import User
from auth.privacy_service import PrivacyService
from auth.profile_service import ProfileService
from auth.rate_limit import AuthRateLimiter
from auth.service import AuthService
from config.settings.api import ApiSettings
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory
from observability.logging import get_logger

_bearer = HTTPBearer(auto_error=False)
_logger = get_logger(__name__)

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


@lru_cache(maxsize=1)
def get_impersonation_store() -> ImpersonationStore | None:
    settings = get_api_settings()
    if not settings.redis_url:
        return None
    return ImpersonationStore(settings.redis_url)


@lru_cache(maxsize=1)
def get_mobile_handoff_store() -> MobileHandoffStore:
    settings = get_api_settings()
    if not settings.redis_url:
        msg = "REDIS_URL is required for the mobile Google login handoff"
        raise RuntimeError(msg)
    return MobileHandoffStore(settings.redis_url)


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
    """Return the peer address already normalized by the trusted ASGI layer.

    Forwarding headers are intentionally not parsed here: accepting a client-
    supplied ``X-Forwarded-For`` would let callers choose the rate-limit key.
    Deployments behind a reverse proxy must configure Uvicorn's trusted
    ``FORWARDED_ALLOW_IPS`` policy so it rewrites ``request.client`` only for
    connections from that proxy.
    """
    if request.client is not None:
        return request.client.host
    return "unknown"


def _family_closed(session: Session, access_session: object) -> bool:
    """Vero se nella catena di rinnovi non resta nessuna sessione attiva."""
    from sqlalchemy import select

    from auth.models.auth_session import AuthSession

    family = getattr(access_session, "family_id", None) or getattr(access_session, "id", None)
    active = session.scalar(
        select(AuthSession.id)
        .where(AuthSession.family_id == family, AuthSession.revoked_at.is_(None))
        .limit(1)
    )
    return active is None


def _note_app_usage(
    request: Request, background_tasks: BackgroundTasks, user: User, *, impersonated: bool
) -> None:
    """Versione dell'app di chi fa la richiesta (release 1.4): scritta dopo la risposta.

    Mai un errore verso il chiamante: se qualcosa va storto si scrive solo nel log.
    """
    if impersonated:
        # Impersonando, l'app è quella dell'operatore: non dice nulla dell'utente.
        return
    try:
        from app_usage.recorder import observe, record_app_usage, should_record

        observation = observe(request.headers, method=request.method, path=request.url.path)
        if observation is None:
            return
        now = datetime.now(UTC)
        if should_record(user.id, observation, now=now):
            background_tasks.add_task(
                record_app_usage, _get_session_factory(), user.id, observation, now=now
            )
    except Exception:
        _logger.warning("app_usage_note_failed", exc_info=True)


def get_current_user(
    request: Request,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
    impersonation_store: ImpersonationStore | None = Depends(get_impersonation_store),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise SessionRequiredError()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.resolved_jwt_secret(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        raise SessionRequiredError() from exc
    if payload.get("type") != "access":
        raise SessionRequiredError()
    if payload.get("imp") is True:
        jti = payload.get("jti")
        if not jti or (impersonation_store is not None and not impersonation_store.is_active(jti)):
            raise SessionRequiredError()
    user_id = UUID(str(payload["sub"]))
    sid = payload.get("sid")
    if sid:
        from auth.models.auth_session import AuthSession

        try:
            access_session = session.get(AuthSession, UUID(str(sid)))
        except ValueError as exc:
            raise SessionRequiredError() from exc
        # Sessione chiusa (logout o revoca): il token d'accesso non vale più. La sessione
        # resta valida se è stata solo ruotata dal rinnovo (la nuova ha lo stesso family_id).
        if access_session is None or (
            access_session.revoked_at is not None and _family_closed(session, access_session)
        ):
            raise SessionRequiredError()
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise SessionRequiredError()
    if BlockList(session).is_blocked(user.email):
        raise AccountBlockedError()
    _note_app_usage(request, background_tasks, user, impersonated=payload.get("imp") is True)
    return user
