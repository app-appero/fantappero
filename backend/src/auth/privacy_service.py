"""Privacy domain service — data export, account deletion, audit (EP02-04)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.auth_session import AuthSession
from auth.models.auth_token import AuthToken
from auth.models.privacy_audit_event import PrivacyAuditEvent
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.privacy_schemas import PrivacyMessageResponse
from auth.privacy_validators import (
    build_anonymized_email,
    require_matching_password,
    resolve_historical_display_name,
    validate_delete_confirmation,
)
from auth.security import hash_password, utc_now, verify_password
from config.settings.api import ApiSettings
from database.enums import PrivacyAuditAction
from leagues.models.league_membership import LeagueMembership
from observability.context import get_correlation_id
from observability.metrics import get_metrics


class PrivacyService:
    """Coordinates GDPR export, anonymized deletion, and privacy audit events."""

    EXPORT_FORMAT_VERSION = "1"

    def __init__(self, session: Session, settings: ApiSettings) -> None:
        self._session = session
        self._settings = settings

    def export_user_data(self, user: User) -> dict[str, Any]:
        loaded = self._load_user_bundle(user.id)
        payload = self._build_export_payload(loaded)
        self._record_audit_event(
            user_id=loaded.id,
            actor_id=loaded.id,
            action=PrivacyAuditAction.DATA_EXPORT,
        )
        self._session.commit()
        get_metrics().incr("privacy_export_total", labels={"result": "success"})
        return payload

    def delete_account(
        self,
        user: User,
        *,
        password: str,
        confirm_phrase: str,
    ) -> PrivacyMessageResponse:
        validate_delete_confirmation(confirm_phrase)
        loaded = self._load_user_bundle(user.id)
        if loaded.deleted_at is not None:
            raise ValidationAuthError(
                "Questo account è già stato eliminato.",
                code="account_already_deleted",
            )

        require_matching_password(
            password_valid=verify_password(loaded.password_hash, password),
        )

        historical_label = resolve_historical_display_name(
            profile_name=loaded.profile.display_name if loaded.profile else None,
            email=loaded.email,
        )
        self._anonymize_competitive_records(loaded.id, historical_label)
        self._scrub_personal_data(loaded)
        self._revoke_all_sessions(loaded.id)
        self._invalidate_all_tokens(loaded.id)
        self._delete_avatar_files(loaded.id)

        self._record_audit_event(
            user_id=loaded.id,
            actor_id=loaded.id,
            action=PrivacyAuditAction.ACCOUNT_DELETE,
        )
        self._session.commit()
        get_metrics().incr("privacy_delete_total", labels={"result": "success"})
        return PrivacyMessageResponse(
            message=(
                "Account eliminato. I dati personali sono stati rimossi "
                "e gli storici di lega sono stati preservati."
            ),
        )

    def _load_user_bundle(self, user_id: UUID) -> User:
        loaded = self._session.scalar(
            select(User)
            .options(
                selectinload(User.profile),
                selectinload(User.league_memberships).selectinload(LeagueMembership.league),
            )
            .where(User.id == user_id),
        )
        if loaded is None:
            msg = "User not found"
            raise RuntimeError(msg)
        if loaded.profile is None:
            profile = UserProfile(user_id=loaded.id)
            self._session.add(profile)
            self._session.flush()
            loaded.profile = profile
        return loaded

    def _build_export_payload(self, user: User) -> dict[str, Any]:
        profile = user.profile
        assert profile is not None
        consent_at = profile.policy_consent_at
        return {
            "exportedAt": utc_now().isoformat(),
            "formatVersion": self.EXPORT_FORMAT_VERSION,
            "account": {
                "id": str(user.id),
                "email": user.email,
                "emailVerifiedAt": user.email_verified_at.isoformat()
                if user.email_verified_at is not None
                else None,
                "platformRole": user.platform_role.value,
                "createdAt": user.created_at.isoformat(),
                "updatedAt": user.updated_at.isoformat(),
            },
            "profile": {
                "displayName": profile.display_name or user.display_name,
                "avatarUrl": profile.avatar_url,
                "language": profile.language,
                "timezone": profile.timezone,
                "notificationsEmail": profile.notifications_email,
                "notificationsPush": profile.notifications_push,
                "policyConsentAt": consent_at.isoformat() if consent_at is not None else None,
                "policyVersion": profile.policy_version,
            },
            "leagueMemberships": [
                {
                    "membershipId": str(membership.id),
                    "leagueId": str(membership.league_id),
                    "leagueName": membership.league.name,
                    "seasonYear": membership.league.season_year,
                    "leagueState": membership.league.state.value,
                    "role": membership.role.value,
                    "historicalDisplayName": membership.historical_display_name,
                    "joinedAt": membership.created_at.isoformat(),
                }
                for membership in user.league_memberships
            ],
        }

    def _anonymize_competitive_records(self, user_id: UUID, historical_label: str) -> None:
        memberships = self._session.scalars(
            select(LeagueMembership).where(LeagueMembership.user_id == user_id),
        ).all()
        for membership in memberships:
            if membership.historical_display_name is None:
                membership.historical_display_name = historical_label

    def _scrub_personal_data(self, user: User) -> None:
        profile = user.profile
        assert profile is not None
        user.email = build_anonymized_email(user.id)
        user.password_hash = hash_password(generate_unusable_secret())
        user.email_verified_at = None
        user.deleted_at = utc_now()
        profile.display_name = None
        profile.avatar_url = None
        profile.notifications_email = False
        profile.notifications_push = False
        profile.policy_consent_at = None
        profile.policy_version = None

    def _record_audit_event(
        self,
        *,
        user_id: UUID,
        actor_id: UUID,
        action: PrivacyAuditAction,
    ) -> None:
        self._session.add(
            PrivacyAuditEvent(
                user_id=user_id,
                actor_id=actor_id,
                action=action,
                correlation_id=get_correlation_id(),
            ),
        )

    def _revoke_all_sessions(self, user_id: UUID) -> None:
        now = utc_now()
        rows = self._session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            ),
        ).all()
        for row in rows:
            row.revoked_at = now

    def _invalidate_all_tokens(self, user_id: UUID) -> None:
        now = utc_now()
        rows = self._session.scalars(
            select(AuthToken).where(
                AuthToken.user_id == user_id,
                AuthToken.used_at.is_(None),
            ),
        ).all()
        for row in rows:
            row.used_at = now

    def _delete_avatar_files(self, user_id: UUID) -> None:
        storage_dir = Path(self._settings.avatar_storage_path)
        if not storage_dir.exists():
            return
        for existing in storage_dir.glob(f"{user_id}.*"):
            if existing.is_file():
                existing.unlink()


def generate_unusable_secret() -> str:
    """Return a random secret that cannot be supplied by an end user."""
    from auth.security import generate_opaque_token

    return generate_opaque_token()
