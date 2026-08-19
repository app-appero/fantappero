"""Schemi HTTP per il pannello qualità dati (EP04-07)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from auth.schemas import ApiModel


class QualitySummaryResponse(ApiModel):
    open_total: int = Field(alias="openTotal")
    by_kind: dict[str, int] = Field(alias="byKind")
    by_severity: dict[str, int] = Field(alias="bySeverity")
    by_status: dict[str, int] = Field(alias="byStatus")


class QualityIssueResponse(ApiModel):
    id: str
    fingerprint: str
    kind: str
    code: str
    severity: str
    status: str
    title: str
    message: str
    fixture_id: str | None = Field(default=None, alias="fixtureId")
    fixture_provider_id: int | None = Field(default=None, alias="fixtureProviderId")
    details: dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(alias="detectedAt")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")
    last_seen_at: datetime = Field(alias="lastSeenAt")


class QualityScanRequest(ApiModel):
    fixture_id: UUID | None = Field(default=None, alias="fixtureId")


class QualityScanResponse(ApiModel):
    fixtures_scanned: int = Field(alias="fixturesScanned")
    findings: int
    issues_created: int = Field(alias="issuesCreated")
    issues_updated: int = Field(alias="issuesUpdated")
    issues_resolved: int = Field(alias="issuesResolved")


class SyncRetryRequest(ApiModel):
    fixture_provider_id: int | None = Field(default=None, alias="fixtureProviderId")


class SyncRetryResponse(ApiModel):
    id: str
    issue_id: str | None = Field(default=None, alias="issueId")
    fixture_id: str | None = Field(default=None, alias="fixtureId")
    fixture_provider_id: int = Field(alias="fixtureProviderId")
    status: str
    trigger: str
    counters: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    started_at: datetime = Field(alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
