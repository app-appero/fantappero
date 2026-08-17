"""Schemi HTTP per il voto statistico (EP07-01)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from auth.schemas import ApiModel


class ComputeRatingsRequest(ApiModel):
    fixture_id: UUID | None = Field(default=None, alias="fixtureId")
    fixture_provider_id: int | None = Field(default=None, alias="fixtureProviderId")
    league_id: UUID | None = Field(default=None, alias="leagueId")
    minutes_threshold: int | None = Field(default=None, alias="minutesThreshold")


class ComputeRatingsResponse(ApiModel):
    fixture_id: str = Field(alias="fixtureId")
    fixture_provider_id: int = Field(alias="fixtureProviderId")
    formula_version: str = Field(alias="formulaVersion")
    created: int
    updated: int
    unchanged: int
    removed: int
    votes: int


class RatingComponentResponse(ApiModel):
    id: str
    path: str
    raw_value: float = Field(alias="rawValue")
    coeff: float
    uncapped: float
    contribution: float
    max_abs: float = Field(alias="maxAbs")


class PlayerMatchRatingResponse(ApiModel):
    id: str
    fixture_id: str = Field(alias="fixtureId")
    athlete_id: str | None = Field(default=None, alias="athleteId")
    athlete_provider_id: int = Field(alias="athleteProviderId")
    formula_version: str = Field(alias="formulaVersion")
    role: str | None
    minutes: int | None
    eligible: bool
    eligibility_reason: str = Field(alias="eligibilityReason")
    base: float
    raw_before_clamp: float = Field(alias="rawBeforeClamp")
    raw: float
    display: float | None
    stats_hash: str = Field(alias="statsHash")
    formula: dict[str, Any]
    input: dict[str, Any]
    components: list[dict[str, Any]]
    bonus_config_version: str | None = Field(default=None, alias="bonusConfigVersion")
    bonus_malus: list[dict[str, Any]] = Field(default_factory=list, alias="bonusMalus")
    bonus_malus_total: float = Field(default=0.0, alias="bonusMalusTotal")
    fantasy_score: float | None = Field(default=None, alias="fantasyScore")
