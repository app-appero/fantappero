"""Profile read/update and avatar upload."""



from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from authorization.service import AuthorizationService
from config.settings.profile import ProfileSettings
from database.models.accounts import User
from database.models.profiles import UserProfile
from profiles.errors import ProfileValidationError
from profiles.schemas import NotificationPreferences, UpdateProfileRequest, UserProfileResponse
from profiles.validation import (
    ProfileValidationRuleError,
    rule_error_to_profile_error,
    validate_avatar_bytes,
    validate_display_name,
    validate_language,
    validate_timezone,
)


class ProfileService:

    """Domain service for private user profile preferences."""



    def __init__(

        self,

        db: Session,

        settings: ProfileSettings,

        authorization: AuthorizationService,

    ) -> None:

        self._db = db

        self._settings = settings

        self._authorization = authorization



    def get_profile(self, *, actor: User, user_id: uuid.UUID) -> UserProfileResponse:

        user = self._authorization.require_user_profile_read(actor=actor, target_user_id=user_id)

        profile = self._get_or_create_profile(user)

        return self._to_response(user, profile)



    def update_profile(

        self,

        *,

        actor: User,

        user_id: uuid.UUID,

        body: UpdateProfileRequest,

    ) -> UserProfileResponse:

        user = self._authorization.require_user_profile_mutate(actor=actor, target_user_id=user_id)

        profile = self._get_or_create_profile(user)



        try:

            if body.display_name is not None:

                profile.display_name = validate_display_name(body.display_name)

            if body.language is not None:

                profile.language = validate_language(body.language)

            if body.timezone is not None:

                profile.timezone = validate_timezone(body.timezone)

            if body.notifications_email is not None:

                profile.notifications_email = body.notifications_email

            if body.notifications_push is not None:

                profile.notifications_push = body.notifications_push

            if body.clear_avatar:

                profile.avatar_url = None

            if body.accept_policy:

                if not body.policy_version:

                    raise ProfileValidationError("Policy version is required to record consent.")

                if body.policy_version != self._settings.profile_policy_version:

                    raise ProfileValidationError(

                        f"Policy version must be {self._settings.profile_policy_version}."

                    )

                profile.policy_version = body.policy_version

                profile.policy_consent_at = datetime.now(UTC)

        except ProfileValidationRuleError as exc:

            raise rule_error_to_profile_error(exc) from exc



        self._db.add(profile)

        return self._to_response(user, profile)



    def upload_avatar(

        self,

        *,

        actor: User,

        user_id: uuid.UUID,

        content: bytes,

        content_type: str | None,

    ) -> UserProfileResponse:

        user = self._authorization.require_user_profile_mutate(actor=actor, target_user_id=user_id)

        profile = self._get_or_create_profile(user)

        profile.avatar_url = validate_avatar_bytes(

            content=content,

            content_type=content_type,

            max_bytes=self._settings.profile_avatar_max_bytes,

        )

        self._db.add(profile)

        return self._to_response(user, profile)



    def _get_or_create_profile(self, user: User) -> UserProfile:

        if user.profile is not None:

            return user.profile

        profile = UserProfile(user_id=user.id)

        self._db.add(profile)

        self._db.flush()

        return profile



    @staticmethod

    def _to_response(user: User, profile: UserProfile) -> UserProfileResponse:

        return UserProfileResponse(

            id=user.id,

            email=user.email,

            email_verified=user.email_verified_at is not None,

            created_at=user.created_at,

            display_name=profile.display_name,

            avatar_url=profile.avatar_url,

            language=profile.language,

            timezone=profile.timezone,

            notifications=NotificationPreferences(

                email=profile.notifications_email,

                push=profile.notifications_push,

            ),

            policy_consent_at=profile.policy_consent_at,

            policy_version=profile.policy_version,

        )


