"""Pydantic schemas for profile API (EP02-02)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ProfileResponse(ApiModel):
    email: str
    displayName: str
    avatarUrl: str | None = None
    language: str
    timezone: str
    notificationsEmail: bool
    notificationsPush: bool
    quietHoursStartHour: int | None = None
    quietHoursEndHour: int | None = None
    policyConsentAt: str | None = None
    policyVersion: str | None = None
    currentPolicyVersion: str
    userType: str
    availableForInvites: bool


class UpdateProfileRequest(ApiModel):
    display_name: str | None = Field(default=None, alias="displayName")
    language: str | None = None
    timezone: str | None = None
    notifications_email: bool | None = Field(default=None, alias="notificationsEmail")
    notifications_push: bool | None = Field(default=None, alias="notificationsPush")
    quiet_hours_start_hour: int | None = Field(default=None, alias="quietHoursStartHour")
    quiet_hours_end_hour: int | None = Field(default=None, alias="quietHoursEndHour")
    available_for_invites: bool | None = Field(default=None, alias="availableForInvites")


class UpdateInviteAvailabilityRequest(ApiModel):
    available_for_invites: bool = Field(alias="availableForInvites")


class PolicyConsentRequest(ApiModel):
    policy_version: str = Field(alias="policyVersion")
    accepted: bool
