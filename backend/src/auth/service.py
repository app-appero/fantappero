"""Account registration, sessions, and credential recovery."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.email import send_password_reset_email, send_verification_email
from auth.errors import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidSessionError,
    InvalidTokenError,
    RateLimitExceededError,
)
from auth.passwords import hash_password, verify_password
from auth.rate_limit import RateLimiter
from auth.tokens import generate_opaque_token, hash_token
from auth.validation import ValidationRuleError, normalize_email, validate_password
from config.settings.auth import AuthSettings
from database.enums import AuthTokenType
from database.models.accounts import AuthSession, AuthToken, User


class AuthService:
    """Domain service for email/password auth and session lifecycle."""

    def __init__(
        self,
        db: Session,
        settings: AuthSettings,
        rate_limiter: RateLimiter,
    ) -> None:
        self._db = db
        self._settings = settings
        self._rate_limiter = rate_limiter

    def register(
        self,
        *,
        email: str,
        password: str,
        client_key: str,
    ) -> tuple[User, str, datetime]:
        self._enforce_rate_limit("register", client_key)
        try:
            normalized_email = normalize_email(email)
            validate_password(password)
        except ValidationRuleError as exc:
            raise InvalidCredentialsError(exc.message) from exc

        existing = self._db.scalar(select(User).where(User.email == normalized_email))
        if existing is not None and not existing.is_deleted:
            raise EmailAlreadyRegisteredError()

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
        )
        self._db.add(user)
        self._db.flush()

        raw_token, expires_at = self._issue_one_time_token(user, AuthTokenType.EMAIL_VERIFICATION)
        send_verification_email(
            email=user.email,
            token=raw_token,
            base_url=self._settings.auth_public_base_url,
        )
        session_token, session_expires = self._create_session(user)
        return user, session_token, session_expires

    def login(
        self,
        *,
        email: str,
        password: str,
        client_key: str,
    ) -> tuple[User, str, datetime]:
        self._enforce_rate_limit("login", client_key)
        try:
            normalized_email = normalize_email(email)
        except ValidationRuleError as exc:
            raise InvalidCredentialsError() from exc

        user = self._db.scalar(
            select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        )
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        session_token, session_expires = self._create_session(user)
        return user, session_token, session_expires

    def logout(self, *, session: AuthSession) -> None:
        session.revoked_at = datetime.now(UTC)
        self._db.add(session)

    def get_user_from_session(self, raw_token: str) -> tuple[User, AuthSession]:
        token_hash = hash_token(raw_token)
        auth_session = self._db.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )
        if auth_session is None:
            raise InvalidSessionError()
        if auth_session.revoked_at is not None:
            raise InvalidSessionError()
        if auth_session.expires_at <= datetime.now(UTC):
            raise InvalidSessionError()

        user = self._db.get(User, auth_session.user_id)
        if user is None or user.is_deleted:
            raise InvalidSessionError()

        return user, auth_session

    def verify_email(self, *, raw_token: str) -> User:
        token_row = self._consume_one_time_token(raw_token, AuthTokenType.EMAIL_VERIFICATION)
        user = self._db.get(User, token_row.user_id)
        if user is None or user.is_deleted:
            raise InvalidTokenError()
        user.email_verified_at = datetime.now(UTC)
        self._db.add(user)
        return user

    def request_password_reset(self, *, email: str, client_key: str) -> None:
        self._enforce_rate_limit("password_reset", client_key)
        try:
            normalized_email = normalize_email(email)
        except ValidationRuleError:
            return

        user = self._db.scalar(
            select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        )
        if user is None:
            return

        raw_token, _ = self._issue_one_time_token(user, AuthTokenType.PASSWORD_RESET)
        send_password_reset_email(
            email=user.email,
            token=raw_token,
            base_url=self._settings.auth_public_base_url,
        )

    def reset_password(self, *, raw_token: str, new_password: str) -> User:
        try:
            validate_password(new_password)
        except ValidationRuleError as exc:
            raise InvalidTokenError(exc.message) from exc

        token_row = self._consume_one_time_token(raw_token, AuthTokenType.PASSWORD_RESET)
        user = self._db.get(User, token_row.user_id)
        if user is None or user.is_deleted:
            raise InvalidTokenError()

        user.password_hash = hash_password(new_password)
        self._db.add(user)
        self._revoke_all_sessions(user.id)
        return user

    def _create_session(self, user: User) -> tuple[str, datetime]:
        raw_token = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(seconds=self._settings.auth_session_ttl_seconds)
        session = AuthSession(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
        self._db.add(session)
        return raw_token, expires_at

    def _issue_one_time_token(
        self,
        user: User,
        token_type: AuthTokenType,
    ) -> tuple[str, datetime]:
        raw_token = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.auth_one_time_token_ttl_seconds
        )
        row = AuthToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            token_type=token_type,
            expires_at=expires_at,
        )
        self._db.add(row)
        return raw_token, expires_at

    def _consume_one_time_token(self, raw_token: str, token_type: AuthTokenType) -> AuthToken:
        token_hash = hash_token(raw_token)
        row = self._db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.token_type == token_type,
            )
        )
        if row is None or row.used_at is not None or row.expires_at <= datetime.now(UTC):
            raise InvalidTokenError()
        row.used_at = datetime.now(UTC)
        self._db.add(row)
        return row

    def _revoke_all_sessions(self, user_id: uuid.UUID) -> None:
        sessions = self._db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        now = datetime.now(UTC)
        for session in sessions:
            session.revoked_at = now
            self._db.add(session)

    def revoke_all_user_sessions(self, user_id: uuid.UUID) -> None:
        """Public entry point for privacy flows and credential rotation."""

        self._revoke_all_sessions(user_id)

    def _enforce_rate_limit(self, action: str, client_key: str) -> None:
        key = f"auth:{action}:{client_key}"
        allowed = self._rate_limiter.hit(
            key,
            limit=self._settings.auth_rate_limit_max_attempts,
            window_seconds=self._settings.auth_rate_limit_window_seconds,
        )
        if not allowed:
            raise RateLimitExceededError()
