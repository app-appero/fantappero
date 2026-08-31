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
    require_trade_approval: bool = Field(default=False, alias="requireTradeApproval")


class LeagueRulesResponse(ApiModel):
    preset_name: Literal["standard"] = Field(alias="presetName")
    participant_count: int = Field(alias="participantCount")
    participant_min: int = Field(alias="participantMin")
    participant_max: int = Field(alias="participantMax")
    roster: LeagueRosterConfig
    total_credits: int = Field(alias="totalCredits")
    min_fixtures_per_round: int = Field(alias="minFixturesPerRound")
    # Frazione degli 11 titolari che ogni fantallenatore deve poter schierare
    # perché una giornata diventi un Turno Europeo valido.
    turn_coverage_threshold: float = Field(alias="turnCoverageThreshold")
    # Minuti di preavviso prima del kickoff reale del singolo giocatore oltre
    # cui si blocca in formazione (formazione a step, per-atleta).
    lineup_lock_margin_minutes: int = Field(alias="lineupLockMarginMinutes")
    minutes_threshold: int = Field(alias="minutesThreshold")
    max_automatic_substitutions: int = Field(alias="maxAutomaticSubstitutions")
    voluntary_release_refund_percent: int = Field(alias="voluntaryReleaseRefundPercent")
    league_exit_refund_percent: int = Field(alias="leagueExitRefundPercent")
    max_active_trade_proposals_per_team: int = Field(alias="maxActiveTradeProposalsPerTeam")
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
    turn_coverage_threshold: float | None = Field(
        default=None, alias="turnCoverageThreshold"
    )
    lineup_lock_margin_minutes: int | None = Field(
        default=None, alias="lineupLockMarginMinutes"
    )
    minutes_threshold: int | None = Field(default=None, alias="minutesThreshold")
    max_automatic_substitutions: int | None = Field(default=None, alias="maxAutomaticSubstitutions")
    voluntary_release_refund_percent: int | None = Field(
        default=None, alias="voluntaryReleaseRefundPercent"
    )
    league_exit_refund_percent: int | None = Field(default=None, alias="leagueExitRefundPercent")
    max_active_trade_proposals_per_team: int | None = Field(
        default=None, alias="maxActiveTradeProposalsPerTeam"
    )
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
    user_type: Literal["human", "ai"] = Field(alias="userType")
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


class PendingInviteCountResponse(ApiModel):
    """Conteggio inviti nominativi realmente pendenti (EP13-P07).

    Volutamente separato dalle notifiche non lette: sono due grandezze con
    semantiche diverse e possono differire.
    """

    pending_invite_count: int = Field(alias="pendingInviteCount")


class FantasyCoachDirectoryItem(ApiModel):
    user_id: str = Field(alias="userId")
    display_name: str = Field(alias="displayName")
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    user_type: Literal["human", "ai"] = Field(alias="userType")
    available_for_invites: bool = Field(alias="availableForInvites")
    named_invite_status: Literal["pending", "accepted", "declined", "revoked", "expired"] | None = (
        Field(default=None, alias="namedInviteStatus")
    )
    # Preview storico (EP13-P06): solo fatti osservabili. `None` quando il
    # dato non esiste — non va reso come zero.
    member_since: str | None = Field(default=None, alias="memberSince")
    concluded_leagues: int = Field(default=0, alias="concludedLeagues")
    best_position: int | None = Field(default=None, alias="bestPosition")
    history_summary: str = Field(default="Nessuna lega conclusa", alias="historySummary")


class CoachPlacementResponse(ApiModel):
    """Piazzamento in una lega conclusa, senza identificare la lega."""

    season_year: int = Field(alias="seasonYear")
    position: int
    participant_count: int = Field(alias="participantCount")
    played: int
    points: int
    fantasy_points: float = Field(alias="fantasyPoints")


class FantasyCoachProfileResponse(ApiModel):
    """Profilo storico limitato, visibile alla sola directory amministrativa."""

    user_id: str = Field(alias="userId")
    display_name: str = Field(alias="displayName")
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    user_type: Literal["human", "ai"] = Field(alias="userType")
    available_for_invites: bool = Field(alias="availableForInvites")
    named_invite_status: Literal["pending", "accepted", "declined", "revoked", "expired"] | None = (
        Field(default=None, alias="namedInviteStatus")
    )
    member_since: str | None = Field(default=None, alias="memberSince")
    concluded_leagues: int = Field(alias="concludedLeagues")
    best_position: int | None = Field(default=None, alias="bestPosition")
    history_summary: str = Field(alias="historySummary")
    placements: list[CoachPlacementResponse] = Field(default_factory=list)
    placements_page: int = Field(alias="placementsPage")
    placements_page_size: int = Field(alias="placementsPageSize")
    placements_total: int = Field(alias="placementsTotal")


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


class H2HMatchupScoreResponse(ApiModel):
    """Risultato H2H persistito sullo slot (EP07-05), esposto in lettura matchday."""

    home_score: float | None = Field(default=None, alias="homeScore")
    away_score: float | None = Field(default=None, alias="awayScore")
    home_fantasy_goals: int | None = Field(default=None, alias="homeFantasyGoals")
    away_fantasy_goals: int | None = Field(default=None, alias="awayFantasyGoals")
    outcome: Literal["home", "away", "draw"] | None = None
    result_final: bool = Field(alias="resultFinal")
    computed_at: datetime | None = Field(default=None, alias="computedAt")


class H2HCalendarMatchupResponse(ApiModel):
    slot_id: str = Field(alias="slotId")
    slot_index: int = Field(alias="slotIndex")
    is_bye: bool = Field(alias="isBye")
    home_user_id: str = Field(alias="homeUserId")
    home_display_name: str = Field(alias="homeDisplayName")
    home_team_name: str | None = Field(default=None, alias="homeTeamName")
    away_user_id: str | None = Field(default=None, alias="awayUserId")
    away_display_name: str | None = Field(default=None, alias="awayDisplayName")
    away_team_name: str | None = Field(default=None, alias="awayTeamName")
    live: bool = False
    result: H2HMatchupScoreResponse | None = None


class H2HCalendarRoundResponse(ApiModel):
    round_number: int = Field(alias="roundNumber")
    fantasy_round_id: str | None = Field(default=None, alias="fantasyRoundId")
    homologation_status: Literal["provisional", "homologated"] | None = Field(
        default=None, alias="homologationStatus"
    )
    european_turn_status: Literal["scheduled", "open", "locked", "skipped"] | None = Field(
        default=None, alias="europeanTurnStatus"
    )
    # Turno europeo antecedente alla creazione della lega: nessuno scontro,
    # la UI mostra un messaggio invece della lista match (§ numerazione condivisa).
    before_league_creation: bool = Field(default=False, alias="beforeLeagueCreation")
    matchups: list[H2HCalendarMatchupResponse]


class H2HCalendarResponse(ApiModel):
    """Calendario H2H confermato con risultati affiancati (consultazione /turni)."""

    id: str
    league_id: str = Field(alias="leagueId")
    status: Literal["confirmed"]
    format: Literal["single_round_robin"]
    algorithm_version: str = Field(alias="algorithmVersion")
    participant_count: int = Field(alias="participantCount")
    round_count: int = Field(alias="roundCount")
    matchup_count: int = Field(alias="matchupCount")
    bye_count: int = Field(alias="byeCount")
    generated_at: datetime = Field(alias="generatedAt")
    confirmed_at: datetime | None = Field(default=None, alias="confirmedAt")
    live: bool
    rounds: list[H2HCalendarRoundResponse]
    summary: LeagueCalendarSummaryResponse


class H2HPlayerScoreResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    name: str
    photo_url: str | None = Field(default=None, alias="photoUrl")
    role: Literal["P", "D", "C", "A"]
    fantasy_score: float | None = Field(default=None, alias="fantasyScore")
    base_score: float | None = Field(default=None, alias="baseScore")
    bonus_total: float = Field(default=0.0, alias="bonusTotal")
    malus_total: float = Field(default=0.0, alias="malusTotal")
    bonus_malus: list[dict[str, object]] = Field(default_factory=list, alias="bonusMalus")
    real_team_name: str | None = Field(default=None, alias="realTeamName")
    fixture_status: str | None = Field(default=None, alias="fixtureStatus")
    fixture_status_label: str = Field(default="Partita non associata", alias="fixtureStatusLabel")
    score_final: bool = Field(default=False, alias="scoreFinal")
    is_effective_starter: bool = Field(alias="isEffectiveStarter")
    is_bench: bool = Field(alias="isBench")


class H2HSideLineupResponse(ApiModel):
    fantasy_team_id: str | None = Field(default=None, alias="fantasyTeamId")
    team_name: str | None = Field(default=None, alias="teamName")
    display_name: str = Field(alias="displayName")
    module: str | None = None
    lineup_source: Literal["effective", "submitted", "none"] = Field(alias="lineupSource")
    total_score: float | None = Field(default=None, alias="totalScore")
    fantasy_goals: int | None = Field(default=None, alias="fantasyGoals")
    starters: list[H2HPlayerScoreResponse]
    bench: list[H2HPlayerScoreResponse]


class H2HMatchupDetailResponse(ApiModel):
    slot_id: str = Field(alias="slotId")
    league_id: str = Field(alias="leagueId")
    round_number: int = Field(alias="roundNumber")
    fantasy_round_id: str | None = Field(default=None, alias="fantasyRoundId")
    homologation_status: Literal["provisional", "homologated"] | None = Field(
        default=None, alias="homologationStatus"
    )
    european_turn_status: Literal["scheduled", "open", "locked", "skipped"] | None = Field(
        default=None, alias="europeanTurnStatus"
    )
    live: bool
    is_bye: bool = Field(alias="isBye")
    home: H2HSideLineupResponse
    away: H2HSideLineupResponse | None = None
    result: H2HMatchupScoreResponse | None = None


class ComputeRoundResultsRequest(ApiModel):
    formula_version: str | None = Field(default=None, alias="formulaVersion")


class ComputeRoundResultsResponse(ApiModel):
    round_id: str = Field(alias="roundId")
    result_final: bool = Field(alias="resultFinal")
    matchups: int
    created: int
    updated: int
    unchanged: int
    skipped: int


class RoundMatchResultResponse(ApiModel):
    slot_index: int = Field(alias="slotIndex")
    home_membership_id: str = Field(alias="homeMembershipId")
    away_membership_id: str | None = Field(default=None, alias="awayMembershipId")
    home_score: float | None = Field(default=None, alias="homeScore")
    away_score: float | None = Field(default=None, alias="awayScore")
    home_fantasy_goals: int | None = Field(default=None, alias="homeFantasyGoals")
    away_fantasy_goals: int | None = Field(default=None, alias="awayFantasyGoals")
    outcome: str | None = None
    result_final: bool = Field(alias="resultFinal")
    computed_at: datetime | None = Field(default=None, alias="computedAt")


class ComputeStandingsResponse(ApiModel):
    league_id: str = Field(alias="leagueId")
    teams: int
    matches_considered: int = Field(alias="matchesConsidered")
    created: int
    updated: int
    unchanged: int
    removed: int


class CalendarWindowResponse(ApiModel):
    """Una finestra europea con verdetto di eleggibilità e motivo (EP13-P03)."""

    start_at: datetime = Field(alias="startAt")
    end_at: datetime = Field(alias="endAt")
    kind: str
    timezone: str
    fixture_count: int = Field(alias="fixtureCount")
    min_required: int = Field(alias="minRequired")
    eligible: bool
    reason: str | None = None


class CalendarPlannedRoundResponse(ApiModel):
    round_number: int = Field(alias="roundNumber")
    cycle_number: int = Field(alias="cycleNumber")
    cycle_round_number: int = Field(alias="cycleRoundNumber")
    window_start_at: datetime = Field(alias="windowStartAt")
    window_end_at: datetime = Field(alias="windowEndAt")
    window_kind: str = Field(alias="windowKind")


class LeagueCalendarPlanResponse(ApiModel):
    """Diagnostica amministrativa: cosa entra, cosa avanza e perché."""

    algorithm_version: str = Field(alias="algorithmVersion")
    participant_count: int = Field(alias="participantCount")
    cycle_length: int = Field(alias="cycleLength")
    cycle_count: int = Field(alias="cycleCount")
    round_count: int = Field(alias="roundCount")
    matchup_count: int = Field(alias="matchupCount")
    bye_count: int = Field(alias="byeCount")
    eligible_window_count: int = Field(alias="eligibleWindowCount")
    windows_fingerprint: str = Field(alias="windowsFingerprint")
    generatable: bool
    stale: bool
    rounds: list[CalendarPlannedRoundResponse]
    windows_used: list[CalendarWindowResponse] = Field(alias="windowsUsed")
    windows_discarded: list[CalendarWindowResponse] = Field(alias="windowsDiscarded")
    summary: str


class LeagueStandingResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    team_name: str = Field(alias="teamName")
    position: int
    played: int
    won: int
    drawn: int
    lost: int
    fantasy_goals_for: int = Field(alias="fantasyGoalsFor")
    fantasy_goals_against: int = Field(alias="fantasyGoalsAgainst")
    # Fantapunti aggregati (EP13-P02): distinti dai gol fantasy e dai punti
    # di classifica.
    fantasy_points_for: float = Field(default=0.0, alias="fantasyPointsFor")
    fantasy_points_against: float = Field(default=0.0, alias="fantasyPointsAgainst")
    points: int
    computed_at: datetime = Field(alias="computedAt")


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
