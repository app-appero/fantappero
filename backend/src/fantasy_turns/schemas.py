"""HTTP schemas for european fantasy turns (EP06-01)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from auth.schemas import ApiModel


class FantasyTurnFixtureResponse(ApiModel):
    id: str
    fixture_id: str = Field(alias="fixtureId")
    included_reason: str = Field(alias="includedReason")
    excluded_at: datetime | None = Field(default=None, alias="excludedAt")
    kickoff_at: datetime | None = Field(default=None, alias="kickoffAt")
    observed_kickoff_at: datetime | None = Field(default=None, alias="observedKickoffAt")
    lock_latched_at: datetime | None = Field(default=None, alias="lockLatchedAt")
    status_short: str = Field(alias="statusShort")
    home_club_name: str = Field(alias="homeClubName")
    away_club_name: str = Field(alias="awayClubName")
    competition_name: str | None = Field(default=None, alias="competitionName")
    provider_id: int = Field(alias="providerId")


class FantasyTurnSummaryResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    number: int
    kind: str
    window_start_at: datetime = Field(alias="windowStartAt")
    window_end_at: datetime = Field(alias="windowEndAt")
    opens_at: datetime | None = Field(default=None, alias="opensAt")
    closes_at: datetime | None = Field(default=None, alias="closesAt")
    cutoff_at: datetime | None = Field(default=None, alias="cutoffAt")
    status: str
    effective_status: str = Field(alias="effectiveStatus")
    skip_reason: str | None = Field(default=None, alias="skipReason")
    fixture_count: int = Field(alias="fixtureCount")
    generated_at: datetime = Field(alias="generatedAt")
    modification_allowed: bool = Field(alias="modificationAllowed")


class FantasyTurnDetailResponse(FantasyTurnSummaryResponse):
    fixtures: list[FantasyTurnFixtureResponse] = Field(default_factory=list)


class FantasyTurnPreviewResponse(ApiModel):
    kind: str
    window_start_at: datetime = Field(alias="windowStartAt")
    window_end_at: datetime = Field(alias="windowEndAt")
    timezone: str
    eligible_count: int = Field(alias="eligibleCount")
    min_required: int = Field(alias="minRequired")
    threshold_ok: bool = Field(alias="thresholdOk")
    skip_reason: str | None = Field(default=None, alias="skipReason")
    cutoff_at: datetime | None = Field(default=None, alias="cutoffAt")
    fixtures: list[FantasyTurnFixtureResponse] = Field(default_factory=list)


class GenerateFantasyTurnRequest(ApiModel):
    kind: Literal["weekend", "midweek"]
    anchor_date: date = Field(alias="anchorDate")


class ExcludeFantasyTurnFixtureRequest(ApiModel):
    fixture_id: UUID = Field(alias="fixtureId")


class EnsureFantasyTurnsResponse(ApiModel):
    league_id: str = Field(alias="leagueId")
    created: int
    opened: int
    upgraded: int
    duplicates: int
    waiting: int
    horizon_days: int = Field(alias="horizonDays")


class ApplyRoundCorrectionRequest(ApiModel):
    reason: str = Field(min_length=1)


class RoundHomologationResponse(ApiModel):
    round_id: str = Field(alias="roundId")
    homologation_status: Literal["provisional", "homologated"] = Field(alias="homologationStatus")
    homologated_at: datetime | None = Field(default=None, alias="homologatedAt")
    formula_version: str | None = Field(default=None, alias="formulaVersion")
