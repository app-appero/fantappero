"""Profile domain service — preferences, avatar, policy consent (EP02-02)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.profile_schemas import PolicyConsentRequest, ProfileResponse, UpdateProfileRequest
from auth.profile_validators import (
    validate_avatar_upload,
    validate_language,
    validate_policy_version,
    validate_profile_display_name,
    validate_quiet_hour,
    validate_timezone,
)
from auth.security import utc_now
from config.settings.api import ApiSettings
from database.enums import UserType
from observability.metrics import get_metrics


class ProfileService:
    """Manages the authenticated user's profile and avatar storage."""

    def __init__(self, session: Session, settings: ApiSettings) -> None:
        self._session = session
        self._settings = settings

    def get_profile(self, user: User) -> ProfileResponse:
        profile = self._ensure_profile(user)
        return self._to_response(user, profile)

    def update_profile(self, user: User, payload: UpdateProfileRequest) -> ProfileResponse:
        profile = self._ensure_profile(user)
        changed = False

        if payload.display_name is not None:
            profile.display_name = validate_profile_display_name(payload.display_name)
            changed = True
        if payload.language is not None:
            profile.language = validate_language(payload.language)
            changed = True
        if payload.timezone is not None:
            profile.timezone = validate_timezone(payload.timezone)
            changed = True
        if payload.notifications_email is not None:
            profile.notifications_email = payload.notifications_email
            changed = True
        if payload.notifications_push is not None:
            profile.notifications_push = payload.notifications_push
            changed = True
        if "quiet_hours_start_hour" in payload.model_fields_set:
            profile.quiet_hours_start_hour = (
                validate_quiet_hour(payload.quiet_hours_start_hour)
                if payload.quiet_hours_start_hour is not None
                else None
            )
            changed = True
        if "quiet_hours_end_hour" in payload.model_fields_set:
            profile.quiet_hours_end_hour = (
                validate_quiet_hour(payload.quiet_hours_end_hour)
                if payload.quiet_hours_end_hour is not None
                else None
            )
            changed = True
        if payload.available_for_invites is not None:
            self._set_invite_availability(user, profile, payload.available_for_invites)
            changed = True

        if not changed:
            raise ValidationAuthError(
                "Nessuna preferenza da aggiornare.",
                code="empty_update",
            )

        self._session.commit()
        get_metrics().incr("profile_update_total", labels={"result": "success"})
        return self._to_response(user, profile)

    def update_invite_availability(
        self,
        user: User,
        *,
        available_for_invites: bool,
    ) -> ProfileResponse:
        profile = self._ensure_profile(user)
        self._set_invite_availability(user, profile, available_for_invites)
        self._session.commit()
        get_metrics().incr("profile_invite_availability_total", labels={"result": "success"})
        return self._to_response(user, profile)

    @staticmethod
    def _set_invite_availability(
        user: User,
        profile: UserProfile,
        available_for_invites: bool,
    ) -> None:
        if user.user_type == UserType.AI:
            raise ValidationAuthError(
                "Gli account IA non possono modificare la disponibilità agli inviti.",
                code="ai_availability_immutable",
            )
        profile.available_for_invites = available_for_invites

    def upload_avatar(self, user: User, *, data: bytes) -> ProfileResponse:
        profile = self._ensure_profile(user)
        _content_type, extension = validate_avatar_upload(
            data=data,
            max_bytes=self._settings.avatar_max_bytes,
        )

        storage_dir = Path(self._settings.avatar_storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)

        for existing in storage_dir.glob(f"{user.id}.*"):
            if existing.is_file():
                existing.unlink()

        filename = f"{user.id}.{extension}"
        target = storage_dir / filename
        target.write_bytes(data)

        profile.avatar_url = f"/media/avatars/{filename}"
        self._session.commit()
        get_metrics().incr("profile_avatar_upload_total", labels={"result": "success"})
        return self._to_response(user, profile)

    def remove_avatar(self, user: User) -> ProfileResponse:
        profile = self._ensure_profile(user)
        self._delete_avatar_files(user.id)
        profile.avatar_url = None
        self._session.commit()
        get_metrics().incr("profile_avatar_remove_total", labels={"result": "success"})
        return self._to_response(user, profile)

    def record_policy_consent(self, user: User, payload: PolicyConsentRequest) -> ProfileResponse:
        if not payload.accepted:
            raise ValidationAuthError(
                "Devi accettare la policy per continuare.",
                code="policy_not_accepted",
            )

        profile = self._ensure_profile(user)
        profile.policy_version = validate_policy_version(
            payload.policy_version,
            self._settings.profile_policy_version,
        )
        profile.policy_consent_at = utc_now()
        self._session.commit()
        get_metrics().incr("profile_policy_consent_total", labels={"result": "success"})
        return self._to_response(user, profile)

    def _ensure_profile(self, user: User) -> UserProfile:
        loaded = self._session.scalar(
            select(User).options(selectinload(User.profile)).where(User.id == user.id),
        )
        if loaded is None:
            msg = "User not found"
            raise RuntimeError(msg)
        if loaded.profile is None:
            profile = UserProfile(user_id=loaded.id)
            self._session.add(profile)
            self._session.flush()
            loaded.profile = profile
        return loaded.profile

    def _delete_avatar_files(self, user_id: UUID) -> None:
        storage_dir = Path(self._settings.avatar_storage_path)
        if not storage_dir.exists():
            return
        for existing in storage_dir.glob(f"{user_id}.*"):
            if existing.is_file():
                existing.unlink()

    def _to_response(self, user: User, profile: UserProfile) -> ProfileResponse:
        consent_at = profile.policy_consent_at
        return ProfileResponse(
            email=user.email,
            displayName=profile.display_name or user.display_name,
            avatarUrl=profile.avatar_url,
            language=profile.language,
            timezone=profile.timezone,
            notificationsEmail=profile.notifications_email,
            notificationsPush=profile.notifications_push,
            quietHoursStartHour=profile.quiet_hours_start_hour,
            quietHoursEndHour=profile.quiet_hours_end_hour,
            policyConsentAt=consent_at.isoformat() if consent_at is not None else None,
            policyVersion=profile.policy_version,
            currentPolicyVersion=self._settings.profile_policy_version,
            userType=user.user_type.value,
            availableForInvites=(
                True if user.user_type == UserType.AI else profile.available_for_invites
            ),
        )
