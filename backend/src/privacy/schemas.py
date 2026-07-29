"""Privacy API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from privacy.anonymization import EXPORT_FORMAT_VERSION


class ExportAccountSection(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    created_at: datetime
    deleted_at: datetime | None = None


class ExportProfileSection(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None
    language: str
    timezone: str
    notifications_email: bool
    notifications_push: bool
    policy_consent_at: datetime | None
    policy_version: str | None
    avatar_present: bool


class ExportLeagueMembershipSection(BaseModel):
    league_id: uuid.UUID
    league_name: str
    role: str
    joined_at: datetime
    historical_display_name: str | None = None


class ExportSessionSection(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class ExportCompetitiveSummary(BaseModel):
    league_memberships_preserved: int
    competitive_tables_present: bool


class UserDataExportResponse(BaseModel):
    format_version: str = Field(default=EXPORT_FORMAT_VERSION)
    exported_at: datetime
    account: ExportAccountSection
    profile: ExportProfileSection
    league_memberships: list[ExportLeagueMembershipSection]
    sessions: list[ExportSessionSection]
    competitive_summary: ExportCompetitiveSummary


class DeleteAccountRequest(BaseModel):
    password: str
    confirm: bool = Field(description="Must be true to proceed with irreversible deletion.")


class DeleteAccountResponse(BaseModel):
    message: str
