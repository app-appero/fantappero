"""Profile and avatar storage configuration (EP02-02)."""

from __future__ import annotations

from pydantic import Field, field_validator


class ProfileSettingsMixin:
    """Avatar storage and privacy policy version knobs."""

    avatar_storage_path: str = Field(
        default="/data/avatars",
        validation_alias="AVATAR_STORAGE_PATH",
        description="Local directory for uploaded avatar files.",
    )
    avatar_max_bytes: int = Field(
        default=2_097_152,
        validation_alias="AVATAR_MAX_BYTES",
        description="Maximum avatar upload size in bytes (default 2 MiB).",
    )
    profile_policy_version: str = Field(
        default="2026-01",
        validation_alias="PROFILE_POLICY_VERSION",
        description="Current privacy policy version users must accept.",
    )

    @field_validator("avatar_max_bytes", mode="before")
    @classmethod
    def _parse_avatar_max_bytes(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return value
