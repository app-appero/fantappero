"""HTTP schemas for trade proposals (EP08-05 / FR-MKT-03)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class CreateTradeProposalRequest(ApiModel):
    recipient_team_id: str = Field(alias="recipientTeamId", min_length=1)
    offered_athlete_ids: list[str] = Field(default_factory=list, alias="offeredAthleteIds")
    requested_athlete_ids: list[str] = Field(default_factory=list, alias="requestedAthleteIds")
    offered_credits: int = Field(default=0, alias="offeredCredits", ge=0)
    requested_credits: int = Field(default=0, alias="requestedCredits", ge=0)
    expires_at: str = Field(alias="expiresAt", min_length=1)


class CounterTradeProposalRequest(ApiModel):
    """Same shape as a fresh proposal; the recipient becomes the new proposer."""

    offered_athlete_ids: list[str] = Field(default_factory=list, alias="offeredAthleteIds")
    requested_athlete_ids: list[str] = Field(default_factory=list, alias="requestedAthleteIds")
    offered_credits: int = Field(default=0, alias="offeredCredits", ge=0)
    requested_credits: int = Field(default=0, alias="requestedCredits", ge=0)
    expires_at: str = Field(alias="expiresAt", min_length=1)


class TradeAthleteResponse(ApiModel):
    id: str
    name: str


class TradeProposalResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    proposer_team_id: str = Field(alias="proposerTeamId")
    recipient_team_id: str = Field(alias="recipientTeamId")
    offered_athletes: list[TradeAthleteResponse] = Field(
        default_factory=list, alias="offeredAthletes"
    )
    requested_athletes: list[TradeAthleteResponse] = Field(
        default_factory=list, alias="requestedAthletes"
    )
    offered_credits: int = Field(alias="offeredCredits")
    requested_credits: int = Field(alias="requestedCredits")
    status: str
    expires_at: str = Field(alias="expiresAt")
    created_at: str = Field(alias="createdAt")
    counter_of_id: str | None = Field(default=None, alias="counterOfId")


class TradeProposalListResponse(ApiModel):
    proposals: list[TradeProposalResponse] = Field(default_factory=list)
