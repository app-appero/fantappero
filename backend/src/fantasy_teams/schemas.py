"""HTTP schemas for fantasy teams, roster slots and credits (EP05-01/02/03/05)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class FantasyRosterSlotResponse(ApiModel):
    id: str
    slot_index: int = Field(alias="slotIndex")
    athlete_id: str | None = Field(default=None, alias="athleteId")
    athlete_name: str | None = Field(default=None, alias="athleteName")
    club_name: str | None = Field(default=None, alias="clubName")
    role: str | None = None
    purchase_credits: int | None = Field(default=None, alias="purchaseCredits")


class RosterCompositionLimitsResponse(ApiModel):
    roster_size: int = Field(alias="rosterSize")
    goalkeepers: int
    defenders: int
    midfielders: int
    forwards: int


class RosterCompositionCountsResponse(ApiModel):
    P: int = 0
    D: int = 0
    C: int = 0
    A: int = 0


class RosterCompositionIssueResponse(ApiModel):
    code: str
    message: str


class RosterCompositionResponse(ApiModel):
    status: str
    filled_slots: int = Field(alias="filledSlots")
    competition_count: int = Field(alias="competitionCount")
    require_complete: bool = Field(alias="requireComplete")
    validated_at: str | None = Field(default=None, alias="validatedAt")
    limits: RosterCompositionLimitsResponse
    counts: RosterCompositionCountsResponse
    issues: list[RosterCompositionIssueResponse] = Field(default_factory=list)


class FantasyTeamResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    membership_id: str = Field(alias="membershipId")
    user_id: str = Field(alias="userId")
    name: str
    roster_size: int = Field(alias="rosterSize")
    filled_slots: int = Field(alias="filledSlots")
    composition_status: str = Field(alias="compositionStatus")
    composition: RosterCompositionResponse | None = None
    slots: list[FantasyRosterSlotResponse] = Field(default_factory=list)


class FantasyTeamSummaryResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    membership_id: str = Field(alias="membershipId")
    user_id: str = Field(alias="userId")
    name: str
    roster_size: int = Field(alias="rosterSize")
    filled_slots: int = Field(alias="filledSlots")
    composition_status: str = Field(alias="compositionStatus")


class EnsureFantasyTeamsResponse(ApiModel):
    created: int
    existing: int
    teams: list[FantasyTeamSummaryResponse] = Field(default_factory=list)


class AssignRosterSlotRequest(ApiModel):
    athlete_id: str = Field(alias="athleteId", min_length=1)
    purchase_credits: int = Field(alias="purchaseCredits", ge=0)


class RosterOccupancyEntryResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    team_name: str = Field(alias="teamName")
    slot_index: int = Field(alias="slotIndex")
    purchase_credits: int | None = Field(default=None, alias="purchaseCredits")


class CreditAccountResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    balance: int
    version: int
    reconstructed_balance: int = Field(alias="reconstructedBalance")


class CreditLedgerEntryResponse(ApiModel):
    id: str
    amount: int
    reason: str
    transaction_id: str = Field(alias="transactionId")
    balance_after: int = Field(alias="balanceAfter")
    note: str | None = None
    actor_id: str | None = Field(default=None, alias="actorId")
    created_at: str = Field(alias="createdAt")


class CreditLedgerListResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    balance: int
    version: int
    entries: list[CreditLedgerEntryResponse] = Field(default_factory=list)


class AdminCreditMovementRequest(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId", min_length=1)
    amount: int
    transaction_id: str = Field(alias="transactionId", min_length=1, max_length=128)
    note: str | None = Field(default=None, max_length=255)


class RosterImportIssueResponse(ApiModel):
    code: str
    message: str
    severity: str


class RosterImportAthleteCandidateResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    provider_id: int = Field(alias="providerId")
    canonical_name: str = Field(alias="canonicalName")


class RosterImportRowResponse(ApiModel):
    row_number: int = Field(alias="rowNumber")
    squadra: str
    provider_id: int | None = Field(default=None, alias="providerId")
    nome: str
    crediti: int | None = None
    status: str
    fantasy_team_id: str | None = Field(default=None, alias="fantasyTeamId")
    fantasy_team_name: str | None = Field(default=None, alias="fantasyTeamName")
    athlete_id: str | None = Field(default=None, alias="athleteId")
    athlete_name: str | None = Field(default=None, alias="athleteName")
    slot_index: int | None = Field(default=None, alias="slotIndex")
    issues: list[RosterImportIssueResponse] = Field(default_factory=list)
    candidates: list[RosterImportAthleteCandidateResponse] = Field(default_factory=list)


class RosterImportPreviewResponse(ApiModel):
    import_id: str = Field(alias="importId")
    status: str
    file_sha256: str = Field(alias="fileSha256")
    original_filename: str | None = Field(default=None, alias="originalFilename")
    can_confirm: bool = Field(alias="canConfirm")
    row_count: int = Field(alias="rowCount")
    error_count: int = Field(alias="errorCount")
    warning_count: int = Field(alias="warningCount")
    rows: list[RosterImportRowResponse] = Field(default_factory=list)
    confirmed_at: str | None = Field(default=None, alias="confirmedAt")


class RosterImportResolutionItem(ApiModel):
    row_number: int = Field(alias="rowNumber", ge=2)
    athlete_id: str = Field(alias="athleteId", min_length=1)


class RosterImportConfirmRequest(ApiModel):
    resolutions: list[RosterImportResolutionItem] = Field(default_factory=list)


class RosterImportTextPreviewRequest(ApiModel):
    csv_text: str = Field(alias="csvText", min_length=1, max_length=512_000)


class RosterImportConfirmResponse(ApiModel):
    import_id: str = Field(alias="importId")
    status: str
    assigned_count: int = Field(alias="assignedCount")
    teams_touched: int = Field(alias="teamsTouched")
    confirmed_at: str = Field(alias="confirmedAt")
    preview: RosterImportPreviewResponse


class RosterOwnershipIntervalResponse(ApiModel):
    id: str
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str | None = Field(default=None, alias="athleteName")
    slot_index: int = Field(alias="slotIndex")
    purchase_credits: int = Field(alias="purchaseCredits")
    acquired_at: str = Field(alias="acquiredAt")
    released_at: str | None = Field(default=None, alias="releasedAt")
    source: str
    active: bool


class RosterOwnershipHistoryResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    intervals: list[RosterOwnershipIntervalResponse] = Field(default_factory=list)


class RosterAsOfSlotResponse(ApiModel):
    slot_index: int = Field(alias="slotIndex")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str | None = Field(default=None, alias="athleteName")
    purchase_credits: int = Field(alias="purchaseCredits")
    acquired_at: str = Field(alias="acquiredAt")
    role: str | None = None


class RosterAsOfResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    as_of: str = Field(alias="asOf")
    filled_slots: int = Field(alias="filledSlots")
    slots: list[RosterAsOfSlotResponse] = Field(default_factory=list)


class CreateRosterTurnSnapshotRequest(ApiModel):
    round_number: int = Field(alias="roundNumber", ge=1)


class RosterTurnSnapshotSummaryResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    round_number: int = Field(alias="roundNumber")
    captured_at: str = Field(alias="capturedAt")
    entry_count: int = Field(alias="entryCount")
    actor_id: str | None = Field(default=None, alias="actorId")


class RosterTurnSnapshotEntryResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    team_name: str = Field(alias="teamName")
    slot_index: int = Field(alias="slotIndex")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str | None = Field(default=None, alias="athleteName")
    purchase_credits: int = Field(alias="purchaseCredits")
    role: str | None = None


class RosterTurnSnapshotDetailResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    round_number: int = Field(alias="roundNumber")
    captured_at: str = Field(alias="capturedAt")
    entry_count: int = Field(alias="entryCount")
    actor_id: str | None = Field(default=None, alias="actorId")
    created: bool = False
    entries: list[RosterTurnSnapshotEntryResponse] = Field(default_factory=list)
