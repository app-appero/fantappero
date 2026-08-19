"""HTTP schemas for the Pro league export (EP11-05)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from auth.schemas import ApiModel
from leagues.schemas import LeagueStandingResponse


class LeagueProExportResponse(ApiModel):
    league_id: str = Field(alias="leagueId")
    generated_at: datetime = Field(alias="generatedAt")
    standings: list[LeagueStandingResponse]
    audit_events_count: int = Field(alias="auditEventsCount")
