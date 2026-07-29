"""Pydantic schemas for league endpoints (EP03-01)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class CompetitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: int
    name: str
    country: str


class CreateLeagueRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    season_year: int = Field(ge=2020, le=2035)
    competition_ids: list[uuid.UUID] = Field(min_length=3, max_length=5)


class UpdateLeagueRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class LeagueCompetitionSummary(BaseModel):
    id: uuid.UUID
    provider_id: int
    name: str
    country: str


class LeagueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    season_year: int
    state: str
    role: str | None = None
    competitions: list[LeagueCompetitionSummary] = Field(default_factory=list)
