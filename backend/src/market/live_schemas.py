"""HTTP schemas for the live/ascending auction mode (EP08-09)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class CreateLiveAuctionSessionRequest(ApiModel):
    opens_at: str = Field(alias="opensAt", min_length=1)
    closes_at: str = Field(alias="closesAt", min_length=1)
    # "manual" | "sequential" | "turn_based" | "alphabetical_by_role" | "random"
    nomination_mode: str = Field(alias="nominationMode")
    min_increment_credits: int = Field(alias="minIncrementCredits", ge=1)
    soft_close_seconds: int = Field(alias="softCloseSeconds", ge=5, le=120)
    lot_duration_seconds: int = Field(alias="lotDurationSeconds", ge=10, le=300)
    operator_user_id: str | None = Field(default=None, alias="operatorUserId")
    # Required, non-empty, iff nominationMode == "sequential". Ignored (must be
    # empty/omitted) for every other mode — "turn_based", "alphabetical_by_role"
    # and "random" all build their own queue/rotation server-side.
    nomination_queue_athlete_ids: list[str] | None = Field(
        default=None, alias="nominationQueueAthleteIds"
    )


class ConfigureLiveAuctionSessionRequest(ApiModel):
    min_increment_credits: int | None = Field(default=None, alias="minIncrementCredits", ge=1)
    soft_close_seconds: int | None = Field(default=None, alias="softCloseSeconds", ge=5, le=120)
    lot_duration_seconds: int | None = Field(
        default=None, alias="lotDurationSeconds", ge=10, le=300
    )
    operator_user_id: str | None = Field(default=None, alias="operatorUserId")
    nomination_queue_athlete_ids: list[str] | None = Field(
        default=None, alias="nominationQueueAthleteIds"
    )


class LiveTurnOrderEntryResponse(ApiModel):
    """One seat in the ``turn_based`` rotation (drawn once at session creation)."""

    fantasy_team_id: str = Field(alias="fantasyTeamId")
    fantasy_team_name: str = Field(alias="fantasyTeamName")
    position: int


class LiveAuctionSessionResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    status: str
    opens_at: str = Field(alias="opensAt")
    closes_at: str = Field(alias="closesAt")
    nomination_mode: str = Field(alias="nominationMode")
    min_increment_credits: int = Field(alias="minIncrementCredits")
    soft_close_seconds: int = Field(alias="softCloseSeconds")
    lot_duration_seconds: int = Field(alias="lotDurationSeconds")
    operator_user_id: str | None = Field(default=None, alias="operatorUserId")
    queue_remaining: int = Field(default=0, alias="queueRemaining")
    pending_swap_count: int = Field(default=0, alias="pendingSwapCount")
    # Only populated for nominationMode == "turn_based": the team rotation
    # drawn at creation, in call order.
    turn_order: list[LiveTurnOrderEntryResponse] = Field(default_factory=list, alias="turnOrder")


class NominateLotRequest(ApiModel):
    # Required iff the session's nominationMode is "manual" or "turn_based";
    # ignored for the auto-generated queue modes ("sequential",
    # "alphabetical_by_role", "random").
    athlete_id: str | None = Field(default=None, alias="athleteId")


class PlaceRaiseRequest(ApiModel):
    amount_credits: int = Field(alias="amountCredits", ge=1)


class LiveLotResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    sequence_number: int = Field(alias="sequenceNumber")
    status: str
    opened_at: str = Field(alias="openedAt")
    closes_at: str = Field(alias="closesAt")
    min_increment_credits: int = Field(alias="minIncrementCredits")
    current_leader_team_id: str | None = Field(default=None, alias="currentLeaderTeamId")
    current_leader_team_name: str | None = Field(default=None, alias="currentLeaderTeamName")
    current_amount_credits: int = Field(alias="currentAmountCredits")
    minimum_next_amount_credits: int = Field(alias="minimumNextAmountCredits")
    closed_at: str | None = Field(default=None, alias="closedAt")


class LiveRaiseResponse(ApiModel):
    id: str
    lot_id: str = Field(alias="lotId")
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    fantasy_team_name: str = Field(alias="fantasyTeamName")
    amount_credits: int = Field(alias="amountCredits")
    placed_at: str = Field(alias="placedAt")


class LiveSwapCandidateResponse(ApiModel):
    slot_index: int = Field(alias="slotIndex")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    purchase_credits: int = Field(alias="purchaseCredits")


class PendingSwapResponse(ApiModel):
    lot_id: str = Field(alias="lotId")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    amount_credits: int = Field(alias="amountCredits")
    role: str
    role_label: str = Field(alias="roleLabel")
    candidates: list[LiveSwapCandidateResponse] = Field(default_factory=list)


class ResolveSwapRequest(ApiModel):
    release_athlete_id: str = Field(alias="releaseAthleteId", min_length=1)


class LiveLotStateResponse(ApiModel):
    session: LiveAuctionSessionResponse
    current_lot: LiveLotResponse | None = Field(default=None, alias="currentLot")
    recent_raises: list[LiveRaiseResponse] = Field(default_factory=list, alias="recentRaises")
    seconds_remaining: int | None = Field(default=None, alias="secondsRemaining")
    pending_swap: PendingSwapResponse | None = Field(default=None, alias="pendingSwap")
    # Only meaningful for nominationMode == "turn_based": whose turn it is to
    # call the next lot. Null once the queue/rotation runs out or for every
    # other nomination mode.
    current_turn_team_id: str | None = Field(default=None, alias="currentTurnTeamId")
    current_turn_team_name: str | None = Field(default=None, alias="currentTurnTeamName")


class LiveLotListResponse(ApiModel):
    session_id: str = Field(alias="sessionId")
    lots: list[LiveLotResponse] = Field(default_factory=list)
