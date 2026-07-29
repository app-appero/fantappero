"""Profile-specific domain errors."""

from __future__ import annotations

from auth.errors import AuthError


class ProfileValidationError(AuthError):
    code = "profile_validation_error"
    message = "Profile data is not valid."
    status_code = 400


class InvalidAvatarError(AuthError):
    code = "invalid_avatar"
    message = "Avatar upload is not valid."
    status_code = 400
