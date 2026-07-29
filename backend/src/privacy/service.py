"""Data export and account deletion with competitive-record anonymization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from auth.passwords import hash_password, verify_password
from auth.service import AuthService
from authorization.service import AuthorizationService
from database.enums import PrivacyAuditAction
from database.models.accounts import AuthSession, User
from database.models.leagues import LeagueMembership
from database.models.privacy import PrivacyAuditEvent
from database.models.profiles import UserProfile
from privacy.anonymization import (
    EXPORT_FORMAT_VERSION,
    anonymized_email,
    anonymized_historical_label,
    competitive_records_preserved,
    scrub_profile,
    snapshot_membership_history,
)
from privacy.errors import AccountAlreadyDeletedError, InvalidDeleteConfirmationError
from privacy.schemas import (
    DeleteAccountRequest,
    DeleteAccountResponse,
    ExportAccountSection,
    ExportCompetitiveSummary,
    ExportLeagueMembershipSection,
    ExportProfileSection,
    ExportSessionSection,
    UserDataExportResponse,
)
from privacy.validation import ValidationRuleError, validate_delete_confirmation


class PrivacyService:
    """Domain service for GDPR-style data export and account deletion."""

    def __init__(
        self,
        db: Session,
        authorization: AuthorizationService,
        auth: AuthService,
    ) -> None:
        self._db = db
        self._authorization = authorization
        self._auth = auth

    def export_user_data(
        self,
        *,
        actor: User,
        user_id: uuid.UUID,
        correlation_id: str | None = None,
    ) -> UserDataExportResponse:
        user = self._authorization.require_data_export(actor=actor, target_user_id=user_id)
        profile = self._get_or_create_profile(user)
        memberships = self._load_memberships(user.id)
        sessions = self._db.scalars(
            select(AuthSession).where(AuthSession.user_id == user.id)
        ).all()

        self._record_audit(
            user_id=user.id,
            actor_id=actor.id,
            action=PrivacyAuditAction.DATA_EXPORT,
            correlation_id=correlation_id,
        )

        return UserDataExportResponse(
            format_version=EXPORT_FORMAT_VERSION,
            exported_at=datetime.now(UTC),
            account=ExportAccountSection(
                id=user.id,
                email=user.email,
                email_verified=user.email_verified_at is not None,
                created_at=user.created_at,
                deleted_at=user.deleted_at,
            ),
            profile=ExportProfileSection(
                display_name=profile.display_name,
                language=profile.language,
                timezone=profile.timezone,
                notifications_email=profile.notifications_email,
                notifications_push=profile.notifications_push,
                policy_consent_at=profile.policy_consent_at,
                policy_version=profile.policy_version,
                avatar_present=profile.avatar_url is not None,
            ),
            league_memberships=[
                ExportLeagueMembershipSection(
                    league_id=membership.league_id,
                    league_name=membership.league.name,
                    role=membership.role.value,
                    joined_at=membership.created_at,
                    historical_display_name=membership.historical_display_name,
                )
                for membership in memberships
            ],
            sessions=[
                ExportSessionSection(
                    id=session.id,
                    created_at=session.created_at,
                    expires_at=session.expires_at,
                    revoked_at=session.revoked_at,
                )
                for session in sessions
            ],
            competitive_summary=ExportCompetitiveSummary(
                **competitive_records_preserved(membership_count=len(memberships)),
            ),
        )

    def delete_account(
        self,
        *,
        actor: User,
        user_id: uuid.UUID,
        body: DeleteAccountRequest,
        correlation_id: str | None = None,
    ) -> DeleteAccountResponse:
        user = self._authorization.require_account_delete(actor=actor, target_user_id=user_id)
        if user.is_deleted:
            raise AccountAlreadyDeletedError()

        try:
            validate_delete_confirmation(password=body.password, confirm=body.confirm)
        except ValidationRuleError as exc:
            raise InvalidDeleteConfirmationError(exc.message) from exc

        if not verify_password(body.password, user.password_hash):
            raise InvalidDeleteConfirmationError("Password is incorrect.")

        profile = self._get_or_create_profile(user)
        historical_label = anonymized_historical_label(profile.display_name)
        memberships = self._load_memberships(user.id)

        self._record_audit(
            user_id=user.id,
            actor_id=actor.id,
            action=PrivacyAuditAction.ACCOUNT_DELETE,
            correlation_id=correlation_id,
        )

        for membership in memberships:
            snapshot_membership_history(membership, historical_label=historical_label)
            self._db.add(membership)

        scrub_profile(profile)
        self._db.add(profile)

        user.deleted_at = datetime.now(UTC)
        user.email = anonymized_email(user.id)
        user.password_hash = hash_password(uuid.uuid4().hex)
        user.email_verified_at = None
        self._db.add(user)

        self._auth.revoke_all_user_sessions(user.id)

        return DeleteAccountResponse(message="Account deleted. Personal data has been removed.")

    def _get_or_create_profile(self, user: User) -> UserProfile:
        if user.profile is not None:
            return user.profile
        profile = UserProfile(user_id=user.id)
        self._db.add(profile)
        self._db.flush()
        return profile

    def _load_memberships(self, user_id: uuid.UUID) -> list[LeagueMembership]:
        return list(
            self._db.scalars(
                select(LeagueMembership)
                .options(joinedload(LeagueMembership.league))
                .where(LeagueMembership.user_id == user_id)
                .order_by(LeagueMembership.created_at)
            ).all()
        )

    def _record_audit(
        self,
        *,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: PrivacyAuditAction,
        correlation_id: str | None,
    ) -> None:
        event = PrivacyAuditEvent(
            user_id=user_id,
            actor_id=actor_id,
            action=action,
            correlation_id=correlation_id,
        )
        self._db.add(event)
