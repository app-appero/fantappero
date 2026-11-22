"""HTTP schemas for the sealed-bid market session (EP08-01)."""

from __future__ import annotations

from pydantic import Field, StrictInt

from app.text_validation import AthleteNameStr, NoNulStr
from auth.schemas import ApiModel
from market.gate import MarketBlockedReason
from market.valuation_schemas import AthleteSeasonAverageResponse


class MarketGateResponse(ApiModel):
    market_open: bool = Field(alias="marketOpen")
    # Decisione del 20/11: il mercato si apre solo a lega al completo. Le app mostrano
    # «Il mercato si apre quando la lega è al completo (iscritti/partecipanti).»
    member_count: int = Field(alias="memberCount")
    participant_count: int | None = Field(alias="participantCount")
    league_full: bool = Field(alias="leagueFull")
    market_blocked_reason: MarketBlockedReason | None = Field(alias="marketBlockedReason")
    # Inviti nominativi che tengono un posto (in attesa, non scaduti): le app li mostrano accanto
    # al conto, «(3/4 · 1 invito in attesa)». Non rendono la lega al completo.
    pending_invite_count: int = Field(alias="pendingInviteCount", default=0)


class SetMarketGateRequest(ApiModel):
    open: bool


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
    amount_credits: StrictInt = Field(alias="amountCredits", ge=1, le=2**31 - 1)
    # Required for waiver bids (FR-MKT-01): the roster player to release if won.
    # Must be omitted for initial-auction bids.
    release_athlete_id: NoNulStr | None = Field(default=None, alias="releaseAthleteId")


class MarketBidResponse(ApiModel):
    id: str
    session_id: str = Field(alias="sessionId")
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: AthleteNameStr = Field(alias="athleteName")
    photo_url: str | None = Field(default=None, alias="photoUrl")
    amount_credits: int = Field(alias="amountCredits")
    status: str
    submitted_at: str = Field(alias="submittedAt")
    release_athlete_id: NoNulStr | None = Field(default=None, alias="releaseAthleteId")
    release_athlete_name: AthleteNameStr | None = Field(default=None, alias="releaseAthleteName")
    #: Valore di mercato in crediti di questa lega (budget della lega, almeno 1); ``None`` se il
    #: calciatore non è nel listone della stagione. Prezzo consigliato, non un minimo (1.3).
    market_value: int | None = Field(default=None, alias="marketValue")
    #: Media stagionale (in corso se ha almeno un voto, altrimenti la scorsa, es. «25/26»).
    season_average: AthleteSeasonAverageResponse | None = Field(default=None, alias="seasonAverage")


class MarketBidListResponse(ApiModel):
    session_id: str = Field(alias="sessionId")
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    bids: list[MarketBidResponse] = Field(default_factory=list)


class MarketResolutionOutcomeResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    athlete_name: AthleteNameStr = Field(alias="athleteName")
    outcome: str  # "assigned" | "tiebreak" | "unassigned"
    winning_team_id: str | None = Field(default=None, alias="winningTeamId")
    amount_credits: int | None = Field(default=None, alias="amountCredits")
    tiebreak_session_id: str | None = Field(default=None, alias="tiebreakSessionId")


class MarketResolutionResponse(ApiModel):
    session_id: str = Field(alias="sessionId")
    status: str
    outcomes: list[MarketResolutionOutcomeResponse] = Field(default_factory=list)


class MarketReleaseRequest(ApiModel):
    reason: NoNulStr = Field(min_length=1)  # "voluntary" | "league_exit"
    # Facoltativo: il calciatore che si vuole svincolare. Se lo slot ne contiene un altro (la rosa
    # si è riordinata) la richiesta è rifiutata e non svincola nessuno.
    athlete_id: NoNulStr | None = Field(default=None, alias="athleteId")


class MarketReleasePreviewResponse(ApiModel):
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    slot_index: int = Field(alias="slotIndex")
    athlete_id: str = Field(alias="athleteId")
    athlete_name: AthleteNameStr = Field(alias="athleteName")
    purchase_credits: int = Field(alias="purchaseCredits")
    reason: str
    refund_percent: int = Field(alias="refundPercent")
    refund_credits: int = Field(alias="refundCredits")


class MarketReleaseResultResponse(MarketReleasePreviewResponse):
    balance: int
