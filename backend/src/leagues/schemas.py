"""League HTTP schemas (EP02-03 / EP03-02)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from auth.schemas import ApiModel
from database.enums import LeagueState


class LeagueSummaryResponse(ApiModel):
    id: str
    name: str
    role: str
    state: LeagueState


class CompetitionSummaryResponse(ApiModel):
    id: str
    provider_id: int = Field(alias="providerId")
    name: str
    country: str


class LeagueRosterConfig(ApiModel):
    roster_size: int = Field(alias="rosterSize")
    goalkeepers: int
    defenders: int
    midfielders: int
    forwards: int


class LeagueRulesOptions(ApiModel):
    allow_trades: bool = Field(alias="allowTrades")
    allow_manual_invites: bool = Field(alias="allowManualInvites")


class LeagueRulesResponse(ApiModel):
    preset_name: Literal["standard"] = Field(alias="presetName")
    participant_count: int = Field(alias="participantCount")
    participant_min: int = Field(alias="participantMin")
    participant_max: int = Field(alias="participantMax")
    roster: LeagueRosterConfig
    total_credits: int = Field(alias="totalCredits")
    min_fixtures_per_round: int = Field(alias="minFixturesPerRound")
    minutes_threshold: int = Field(alias="minutesThreshold")
    options: LeagueRulesOptions


class LeagueDetailResponse(ApiModel):
    id: str
    name: str
    season_year: int = Field(alias="seasonYear")
    state: str
    viewer_role: str | None = Field(default=None, alias="viewerRole")
    competitions: list[CompetitionSummaryResponse] = Field(default_factory=list)
    rules: LeagueRulesResponse | None = None


class CreateLeagueRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    season_year: int = Field(alias="seasonYear")
    competition_ids: list[UUID] = Field(min_length=3, alias="competitionIds")


class UpdateLeagueRulesRequest(ApiModel):
    preset_name: Literal["standard"] = Field(default="standard", alias="presetName")
    participant_count: int = Field(alias="participantCount")
    roster: LeagueRosterConfig
    total_credits: int = Field(alias="totalCredits")
    min_fixtures_per_round: int | None = Field(default=None, alias="minFixturesPerRound")
    minutes_threshold: int | None = Field(default=None, alias="minutesThreshold")
    options: LeagueRulesOptions


class LeagueLifecycleBlocker(ApiModel):
    code: str
    message: str


class LeagueLifecycleResponse(ApiModel):
    state: LeagueState
    allowed_transitions: list[LeagueState] = Field(alias="allowedTransitions")
    blockers: list[LeagueLifecycleBlocker] = Field(default_factory=list)


class TransitionLeagueStateRequest(ApiModel):
    target_state: LeagueState = Field(alias="targetState")


class LeagueAdminPanelResponse(ApiModel):
    league_id: str = Field(alias="leagueId")
    message: str
    rules: LeagueRulesResponse
    lifecycle: LeagueLifecycleResponse


class LeagueMemberResponse(ApiModel):
    user_id: str = Field(alias="userId")
    display_name: str = Field(alias="displayName")
    role: Literal["member", "league_admin"]
    joined_at: datetime = Field(alias="joinedAt")


class CreateLeagueInviteRequest(ApiModel):
    expires_in_days: int = Field(default=7, alias="expiresInDays")


class LeagueInviteResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    status: Literal["active", "expired", "revoked"]
    expires_at: datetime = Field(alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    created_at: datetime = Field(alias="createdAt")


class CreateLeagueInviteResponse(LeagueInviteResponse):
    token: str
    code: str
    invite_url: str = Field(alias="inviteUrl")


class AcceptLeagueInviteRequest(ApiModel):
    token: str | None = Field(default=None, max_length=512)
    code: str | None = Field(default=None, max_length=32)


class AcceptLeagueInviteResponse(ApiModel):
    league_id: str = Field(alias="leagueId")
    league_name: str = Field(alias="leagueName")
    already_member: bool = Field(alias="alreadyMember")


class FantasyCoachDirectoryItem(ApiModel):
    user_id: str = Field(alias="userId")
    display_name: str = Field(alias="displayName")
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    user_type: Literal["human", "ai"] = Field(alias="userType")
    available_for_invites: bool = Field(alias="availableForInvites")
    named_invite_status: Literal["pending", "accepted", "declined", "revoked", "expired"] | None = (
        Field(default=None, alias="namedInviteStatus")
    )


class FantasyCoachDirectoryResponse(ApiModel):
    items: list[FantasyCoachDirectoryItem]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")


class CreateNamedLeagueInviteRequest(ApiModel):
    recipient_user_id: UUID = Field(alias="recipientUserId")
    expires_in_days: int = Field(default=7, ge=1, le=30, alias="expiresInDays")


class NamedLeagueInviteResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    league_name: str = Field(alias="leagueName")
    recipient_user_id: str = Field(alias="recipientUserId")
    recipient_display_name: str = Field(alias="recipientDisplayName")
    recipient_user_type: Literal["human", "ai"] = Field(alias="recipientUserType")
    status: Literal["pending", "accepted", "declined", "revoked", "expired"]
    expires_at: datetime = Field(alias="expiresAt")
    responded_at: datetime | None = Field(default=None, alias="respondedAt")
    created_at: datetime = Field(alias="createdAt")
    auto_accepted: bool = Field(default=False, alias="autoAccepted")


class RespondNamedLeagueInviteResponse(NamedLeagueInviteResponse):
    already_processed: bool = Field(alias="alreadyProcessed")


class LeagueCalendarMatchupResponse(ApiModel):
    slot_index: int = Field(alias="slotIndex")
    is_bye: bool = Field(alias="isBye")
    home_user_id: str = Field(alias="homeUserId")
    home_display_name: str = Field(alias="homeDisplayName")
    away_user_id: str | None = Field(default=None, alias="awayUserId")
    away_display_name: str | None = Field(default=None, alias="awayDisplayName")


class LeagueCalendarRoundResponse(ApiModel):
    round_number: int = Field(alias="roundNumber")
    matchups: list[LeagueCalendarMatchupResponse]


class LeagueCalendarSummaryResponse(ApiModel):
    message: str


class LeagueCalendarResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    status: Literal["draft", "confirmed"]
    format: Literal["single_round_robin"]
    algorithm_version: str = Field(alias="algorithmVersion")
    participant_count: int = Field(alias="participantCount")
    round_count: int = Field(alias="roundCount")
    matchup_count: int = Field(alias="matchupCount")
    bye_count: int = Field(alias="byeCount")
    generated_at: datetime = Field(alias="generatedAt")
    confirmed_at: datetime | None = Field(default=None, alias="confirmedAt")
    rounds: list[LeagueCalendarRoundResponse]
    summary: LeagueCalendarSummaryResponse


class LeagueListoneOverrideResponse(ApiModel):
    role: Literal["P", "D", "C", "A"]
    effective_from_round: int | None = Field(alias="effectiveFromRound")
    pending: bool
    reason: str | None = None


class LeagueListoneEntryResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    canonical_name: str = Field(alias="canonicalName")
    season_year: int = Field(alias="seasonYear")
    official_role: Literal["P", "D", "C", "A"] = Field(alias="officialRole")
    effective_role: Literal["P", "D", "C", "A"] = Field(alias="effectiveRole")
    provider_position_raw: str | None = Field(default=None, alias="providerPositionRaw")
    mapping_version: str = Field(alias="mappingVersion")
    club_id: str | None = Field(default=None, alias="clubId")
    club_name: str | None = Field(default=None, alias="clubName")
    override: LeagueListoneOverrideResponse | None = None


class SetLeagueRoleOverrideRequest(ApiModel):
    role: Literal["P", "D", "C", "A"]
    current_round: int | None = Field(default=None, ge=0, alias="currentRound")
    reason: str | None = Field(default=None, max_length=240)


class LeagueListoneRefreshCounters(ApiModel):
    athletes_created: int = Field(alias="athletesCreated")
    athletes_updated: int = Field(alias="athletesUpdated")
    memberships_created: int = Field(alias="membershipsCreated")
    memberships_updated: int = Field(alias="membershipsUpdated")
    transfers_created: int = Field(alias="transfersCreated")
    listone_created: int = Field(alias="listoneCreated")
    listone_updated: int = Field(alias="listoneUpdated")
    listone_unchanged: int = Field(alias="listoneUnchanged")
    listone_skipped_unmapped: int = Field(alias="listoneSkippedUnmapped")
    catalog_synced: bool = Field(alias="catalogSynced")


class LeagueListoneRefreshResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    mapping_version: str = Field(alias="mappingVersion")
    refreshed_at: datetime = Field(alias="refreshedAt")
    message: str
    counters: LeagueListoneRefreshCounters


class LeagueListoneRefreshJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class LeagueListoneRefreshProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    league_id: str = Field(alias="leagueId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: LeagueListoneRefreshResponse | None = None
