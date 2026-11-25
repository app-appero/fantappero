"""HTTP schemas del sostituto dopo uno scambio sbilanciato (1.5, decisione del 25/11)."""

from __future__ import annotations

from pydantic import Field

from app.text_validation import AthleteNameStr
from auth.schemas import ApiModel
from market.trade_schemas import TradeMissingRoleResponse
from market.valuation_schemas import AthleteSeasonAverageResponse


class TradeReplacementPendingResponse(ApiModel):
    """Un posto da riempire: il ruolo che manca e lo scambio che l'ha lasciato vuoto."""

    id: str
    role: str
    trade_proposal_id: str = Field(alias="tradeProposalId")
    created_at: str = Field(alias="createdAt")


class TradeReplacementStatusResponse(ApiModel):
    """I sostituti che la mia squadra deve scegliere (``GET …/mercato/sostituti``)."""

    team_id: str = Field(alias="teamId")
    roster_size: int = Field(alias="rosterSize")
    filled_slots: int = Field(alias="filledSlots")
    balance: int
    pending: list[TradeReplacementPendingResponse] = Field(default_factory=list)
    missing_roles: list[TradeMissingRoleResponse] = Field(
        default_factory=list, alias="missingRoles"
    )
    #: Lo scambio più recente fra quelli da cui vengono i sostituti aperti: chi è arrivato e con
    #: chi, per «Scambio fatto: è arrivato <nome>».
    trade_proposal_id: str | None = Field(default=None, alias="tradeProposalId")
    other_team_name: str | None = Field(default=None, alias="otherTeamName")
    received_athlete_names: list[AthleteNameStr] = Field(
        default_factory=list, alias="receivedAthleteNames"
    )
    received_credits: int = Field(default=0, alias="receivedCredits")
    #: ``round_in_progress``: turno in corso, le rose sono ferme e il sostituto si sceglie dopo
    #: il calcolo del turno (``blockedMessage`` dice quando). ``None``: si può scegliere ora.
    blocked_reason: str | None = Field(default=None, alias="blockedReason")
    blocked_message: str | None = Field(default=None, alias="blockedMessage")


class TradeReplacementCandidateResponse(ApiModel):
    """Un calciatore libero del ruolo che manca, con il prezzo del sostituto (il suo Valore)."""

    athlete_id: str = Field(alias="athleteId")
    name: AthleteNameStr
    photo_url: str | None = Field(default=None, alias="photoUrl")
    club_name: str | None = Field(default=None, alias="clubName")
    role: str
    #: Il Valore del calciatore in questa lega: è il prezzo del sostituto.
    market_value: int = Field(alias="marketValue")
    season_average: AthleteSeasonAverageResponse | None = Field(
        default=None, alias="seasonAverage"
    )
    #: ``False`` se costa più dei crediti rimasti: non si può scegliere.
    affordable: bool


class TradeReplacementCandidateListResponse(ApiModel):
    role: str
    balance: int
    total: int
    candidates: list[TradeReplacementCandidateResponse] = Field(default_factory=list)


class TradeReplacementPurchaseRequest(ApiModel):
    athlete_id: str = Field(alias="athleteId", min_length=1)


class TradeReplacementPurchaseResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    athlete_name: AthleteNameStr = Field(alias="athleteName")
    role: str
    price_credits: int = Field(alias="priceCredits")
    balance: int
    #: I sostituti ancora da scegliere dopo questo acquisto (vuoto: rosa tornata alla misura).
    status: TradeReplacementStatusResponse
