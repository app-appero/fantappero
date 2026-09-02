"""Auth domain service — registration, login, tokens, email triggers."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from auth.models.auth_session import AuthSession
from auth.models.auth_token import AuthToken
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.rate_limit import AuthRateLimiter
from auth.schemas import AuthTokensResponse, MessageResponse, SessionUserResponse
from auth.security import (
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    utc_now,
    verify_password,
)
from auth.validators import validate_display_name, validate_email, validate_password
from config.settings.api import ApiSettings
from database.enums import AuthTokenType, PlatformRole, UserType, platform_role_to_global_role
from mail.tasks import send_message_task
from mail.templates import build_email_verification_message, build_password_reset_message
from observability.metrics import get_metrics
from observability.propagation import celery_task_headers

GENERIC_REGISTER_MESSAGE = (
    "Se l'indirizzo email è valido, riceverai un messaggio con le istruzioni."
)
GENERIC_FORGOT_MESSAGE = (
    "Se l'indirizzo email è registrato, riceverai un messaggio con le istruzioni."
)
GENERIC_RESEND_MESSAGE = GENERIC_REGISTER_MESSAGE


class AuthService:
    """Coordinates auth persistence, tokens, rate limits, and email enqueue."""

    def __init__(
        self,
        session: Session,
        settings: ApiSettings,
        rate_limiter: AuthRateLimiter | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._rate_limiter = rate_limiter

    def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        client_ip: str,
    ) -> MessageResponse:
        normalized_email = validate_email(email)
        validated_password = validate_password(password)
        validated_name = validate_display_name(display_name)

        if self._rate_limiter is not None:
            self._rate_limiter.check(
                endpoint="register",
                key=client_ip,
                limit=self._settings.auth_rate_limit_register_per_hour,
                window_seconds=3600,
            )

        existing = self._session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            if not existing.email_verified:
                self._issue_email_verification(existing)
                self._session.commit()
            get_metrics().incr("auth_register_total", labels={"result": "existing"})
            return MessageResponse(message=GENERIC_REGISTER_MESSAGE)

        user = User(
            email=normalized_email,
            password_hash=hash_password(validated_password),
            platform_role=PlatformRole.USER,
            user_type=UserType.HUMAN,
        )
        self._session.add(user)
        self._session.flush()
        self._session.add(UserProfile(user_id=user.id, display_name=validated_name))
        self._issue_email_verification(user)
        self._session.commit()
        get_metrics().incr("auth_register_total", labels={"result": "success"})
        return MessageResponse(message=GENERIC_REGISTER_MESSAGE)

    def login(
        self,
        *,
        email: str,
        password: str,
        client_ip: str,
        user_agent: str | None,
    ) -> AuthTokensResponse:
        del user_agent
        normalized_email = validate_email(email)

        if self._rate_limiter is not None:
            self._rate_limiter.check(
                endpoint="login",
                key=client_ip,
                limit=self._settings.auth_rate_limit_login_per_minute,
                window_seconds=60,
            )

        user = self._session.scalar(
            select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        )
        if (
            user is None
            or user.user_type == UserType.AI
            or not verify_password(user.password_hash, password)
        ):
            get_metrics().incr("auth_login_total", labels={"result": "failure"})
            raise InvalidCredentialsError()

        if not user.email_verified:
            get_metrics().incr("auth_login_total", labels={"result": "unverified"})
            raise EmailNotVerifiedError()

        tokens = self._create_session(user)
        self._session.commit()
        get_metrics().incr("auth_login_total", labels={"result": "success"})
        return tokens

    def refresh(self, *, refresh_token: str) -> AuthTokensResponse:
        token_hash = hash_opaque_token(refresh_token)
        session_row = self._session.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )
        if session_row is None or session_row.revoked_at is not None:
            raise InvalidCredentialsError()
        if session_row.expires_at <= utc_now():
            raise InvalidCredentialsError()

        user = self._session.get(User, session_row.user_id)
        if user is None or user.deleted_at is not None or user.user_type == UserType.AI:
            raise InvalidCredentialsError()

        session_row.revoked_at = utc_now()
        tokens = self._create_session(user)
        self._session.commit()
        return tokens

    def logout(self, *, refresh_token: str) -> None:
        token_hash = hash_opaque_token(refresh_token)
        session_row = self._session.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )
        if session_row is not None and session_row.revoked_at is None:
            session_row.revoked_at = utc_now()
            self._session.commit()

    def verify_email(self, *, token: str) -> MessageResponse:
        auth_token, user = self._resolve_auth_token(token, AuthTokenType.EMAIL_VERIFICATION)
        if user.email_verified:
            auth_token.used_at = utc_now()
            self._session.commit()
            return MessageResponse(message="Il tuo account è già verificato.")

        user.email_verified_at = utc_now()
        auth_token.used_at = utc_now()
        self._invalidate_active_tokens(
            user.id,
            AuthTokenType.EMAIL_VERIFICATION,
            exclude=auth_token.id,
        )
        self._session.commit()
        return MessageResponse(message="Email verificata con successo. Ora puoi accedere.")

    def resend_verification(self, *, email: str, client_ip: str) -> MessageResponse:
        normalized_email = validate_email(email)

        if self._rate_limiter is not None:
            self._rate_limiter.check(
                endpoint="resend_verification",
                key=AuthRateLimiter.email_key(normalized_email),
                limit=self._settings.auth_rate_limit_resend_verification_per_hour,
                window_seconds=3600,
            )
            self._rate_limiter.check(
                endpoint="resend_verification",
                key=client_ip,
                limit=self._settings.auth_rate_limit_resend_verification_per_hour,
                window_seconds=3600,
            )

        user = self._session.scalar(select(User).where(User.email == normalized_email))
        if user is not None and not user.email_verified:
            self._issue_email_verification(user)
            self._session.commit()
        return MessageResponse(message=GENERIC_RESEND_MESSAGE)

    def forgot_password(self, *, email: str, client_ip: str) -> MessageResponse:
        normalized_email = validate_email(email)

        if self._rate_limiter is not None:
            self._rate_limiter.check(
                endpoint="forgot_password",
                key=AuthRateLimiter.email_key(normalized_email),
                limit=self._settings.auth_rate_limit_forgot_password_per_hour,
                window_seconds=3600,
            )
            self._rate_limiter.check(
                endpoint="forgot_password",
                key=client_ip,
                limit=self._settings.auth_rate_limit_forgot_password_per_hour,
                window_seconds=3600,
            )

        user = self._session.scalar(
            select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        )
        if user is not None:
            self._issue_password_reset(user)
            self._session.commit()
        return MessageResponse(message=GENERIC_FORGOT_MESSAGE)

    def reset_password(self, *, token: str, new_password: str) -> MessageResponse:
        validated_password = validate_password(new_password)
        auth_token, user = self._resolve_auth_token(token, AuthTokenType.PASSWORD_RESET)
        user.password_hash = hash_password(validated_password)
        auth_token.used_at = utc_now()
        self._revoke_all_sessions(user.id)
        self._invalidate_active_tokens(
            user.id,
            AuthTokenType.PASSWORD_RESET,
            exclude=auth_token.id,
        )
        self._session.commit()
        return MessageResponse(
            message="Password aggiornata. Ora puoi accedere con le nuove credenziali.",
        )

    def get_user_by_id(self, user_id: UUID) -> User | None:
        user = self._session.get(User, user_id)
        if user is None or user.deleted_at is not None:
            return None
        return user

    def _create_session(self, user: User) -> AuthTokensResponse:
        refresh_raw = generate_opaque_token()
        refresh_hash = hash_opaque_token(refresh_raw)
        expires_at = utc_now() + timedelta(days=self._settings.jwt_refresh_token_expire_days)
        refresh_row = AuthSession(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
        )
        self._session.add(refresh_row)

        access_token, expires_in = create_access_token(
            user_id=user.id,
            secret=self._settings.resolved_jwt_secret(),
            expire_minutes=self._settings.jwt_access_token_expire_minutes,
        )
        return AuthTokensResponse(
            accessToken=access_token,
            refreshToken=refresh_raw,
            expiresIn=expires_in,
            user=self._to_session_user(user),
        )

    def _issue_email_verification(self, user: User) -> str:
        self._invalidate_active_tokens(user.id, AuthTokenType.EMAIL_VERIFICATION)
        raw_token = generate_opaque_token()
        expires_at = utc_now() + timedelta(
            hours=self._settings.auth_email_verification_expire_hours,
        )
        row = AuthToken(
            user_id=user.id,
            token_type=AuthTokenType.EMAIL_VERIFICATION,
            token_hash=hash_opaque_token(raw_token),
            expires_at=expires_at,
        )
        self._session.add(row)
        base_url = self._settings.web_app_base_url.rstrip("/")
        verify_url = f"{base_url}/accedi/verifica?token={raw_token}"
        message = build_email_verification_message(
            verify_url=verify_url,
            display_name=user.display_name,
        )
        self._enqueue_email(user.email, message, template="email_verification")
        return raw_token

    def _issue_password_reset(self, user: User) -> str:
        self._invalidate_active_tokens(user.id, AuthTokenType.PASSWORD_RESET)
        raw_token = generate_opaque_token()
        expires_at = utc_now() + timedelta(hours=self._settings.auth_password_reset_expire_hours)
        row = AuthToken(
            user_id=user.id,
            token_type=AuthTokenType.PASSWORD_RESET,
            token_hash=hash_opaque_token(raw_token),
            expires_at=expires_at,
        )
        self._session.add(row)
        base = self._settings.web_app_base_url.rstrip("/")
        reset_url = f"{base}/accedi/reimposta-password?token={raw_token}"
        message = build_password_reset_message(reset_url=reset_url, display_name=user.display_name)
        self._enqueue_email(user.email, message, template="password_reset")
        return raw_token

    def _enqueue_email(self, to_email: str, message: Any, *, template: str) -> None:
        import os

        kwargs = {
            "to_email": to_email,
            "subject": message.subject,
            "text_body": message.text_body,
            "html_body": message.html_body,
            "template": template,
        }
        if os.environ.get("FANTAPPERO_ENV", "").lower() == "test":
            send_message_task.apply(kwargs=kwargs)
            return
        send_message_task.apply_async(kwargs=kwargs, headers=celery_task_headers())

    def _resolve_auth_token(
        self,
        token: str,
        token_type: AuthTokenType,
    ) -> tuple[AuthToken, User]:
        token_hash = hash_opaque_token(token)
        auth_token = self._session.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.token_type == token_type,
            )
        )
        if auth_token is None or auth_token.used_at is not None:
            raise InvalidTokenError()
        if auth_token.expires_at <= utc_now():
            raise InvalidTokenError()
        user = self._session.get(User, auth_token.user_id)
        if user is None or user.deleted_at is not None:
            raise InvalidTokenError()
        return auth_token, user

    def _invalidate_active_tokens(
        self,
        user_id: UUID,
        token_type: AuthTokenType,
        *,
        exclude: UUID | None = None,
    ) -> None:
        now = utc_now()
        rows = self._session.scalars(
            select(AuthToken).where(
                AuthToken.user_id == user_id,
                AuthToken.token_type == token_type,
                AuthToken.used_at.is_(None),
            )
        ).all()
        for row in rows:
            if exclude is not None and row.id == exclude:
                continue
            row.used_at = now

    def _revoke_all_sessions(self, user_id: UUID) -> None:
        now = utc_now()
        rows = self._session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        for row in rows:
            row.revoked_at = now

    @staticmethod
    def _to_session_user(user: User) -> SessionUserResponse:
        return SessionUserResponse(
            id=str(user.id),
            displayName=user.display_name,
            globalRole=platform_role_to_global_role(user.platform_role).value,
        )
