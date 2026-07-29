"""Pydantic request/response schemas for profile endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class NotificationPreferences(BaseModel):
    email: bool
    push: bool


class UserProfileResponse(BaseModel):
    """Full self profile including private preferences."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    email_verified: bool
    created_at: datetime
    display_name: str | None = None
    avatar_url: str | None = None
    language: str
    timezone: str
    notifications: NotificationPreferences
    policy_consent_at: datetime | None = None
    policy_version: str | None = None


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    notifications_email: bool | None = None
    notifications_push: bool | None = None
    accept_policy: bool | None = None
    policy_version: str | None = Field(default=None, min_length=1, max_length=32)
    clear_avatar: bool | None = None
