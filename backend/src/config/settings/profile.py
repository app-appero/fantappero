"""Profile settings consumed by the API service."""

from __future__ import annotations

from pydantic import Field

from config.settings.base import BaseAppSettings


class ProfileSettings(BaseAppSettings):
    """Avatar limits and active policy version."""

    profile_avatar_max_bytes: int = Field(
        default=512 * 1024,
        validation_alias="PROFILE_AVATAR_MAX_BYTES",
        ge=1024,
    )
    profile_policy_version: str = Field(
        default="2026-01",
        validation_alias="PROFILE_POLICY_VERSION",
        min_length=1,
        max_length=32,
    )
