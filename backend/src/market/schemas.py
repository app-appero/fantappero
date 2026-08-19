"""HTTP schemas for the sealed-bid market session (EP08-01)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class CreateMarketSessionRequest(ApiModel):
    opens_at: str = Field(alias="opensAt", min_length=1)
    closes_at: str = Field(alias="closesAt", min_length=1)


class MarketSessionResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    kind: str
    status: str
    opens_at: str = Field(alias="opensAt")
    closes_at: str = Field(alias="closesAt")
    bid_count: int | None = Field(default=None, alias="bidCount")
    parent_session_id: str | None = Field(default=None, alias="parentSessionId")
    target_athlete_id: str | None = Field(default=None, alias="targetAthleteId")


class SubmitMarketBidRequest(ApiModel):
    amount_credits: int = Field(alias="amountCredits", ge=1)
    # Required for waiver bids (FR-MKT-01): the roster player to release if won.
    # Must be omitted for initial-auction bids.
    release_athlete_id: str | None = Field(default=None, alias="releaseAthleteId")


class MarketBidResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    amount_credits: int = Field(alias="amountCredits")
    status: str
    submitted_at: str = Field(alias="submittedAt")
    release_athlete_id: str | None = Field(default=None, alias="releaseAthleteId")
    release_athlete_name: str | None = Field(default=None, alias="releaseAthleteName")


class MarketBidListResponse(ApiModel):
    session_id: str = Field(alias="sessionId")
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    bids: list[MarketBidResponse] = Field(default_factory=list)


class MarketResolutionOutcomeResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    outcome: str  # "assigned" | "tiebreak" | "unassigned"
    winning_team_id: str | None = Field(default=None, alias="winningTeamId")
    amount_credits: int | None = Field(default=None, alias="amountCredits")
    tiebreak_session_id: str | None = Field(default=None, alias="tiebreakSessionId")


class MarketResolutionResponse(ApiModel):
    session_id: str = Field(alias="sessionId")
    status: str
    outcomes: list[MarketResolutionOutcomeResponse] = Field(default_factory=list)


class MarketReleaseRequest(ApiModel):
    reason: str = Field(min_length=1)  # "voluntary" | "league_exit"


class MarketReleasePreviewResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    slot_index: int = Field(alias="slotIndex")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    purchase_credits: int = Field(alias="purchaseCredits")
    reason: str
    refund_percent: int = Field(alias="refundPercent")
    refund_credits: int = Field(alias="refundCredits")


class MarketReleaseResultResponse(MarketReleasePreviewResponse):
    balance: int
