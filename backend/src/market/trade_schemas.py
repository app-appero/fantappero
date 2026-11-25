"""HTTP schemas for trade proposals (EP08-05 / FR-MKT-03)."""

from __future__ import annotations

from pydantic import Field

from app.text_validation import AthleteNameStr
from auth.schemas import ApiModel
from fantasy_teams.schemas import RosterUnderQuotaRoleResponse
from market.valuation_schemas import AthleteSeasonAverageResponse

# Tetto tecnico (colonne a 32 bit): oltre, la richiesta è respinta con 422.
MAX_TRADE_CREDITS = 1_000_000


class CreateTradeProposalRequest(ApiModel):
    recipient_team_id: str = Field(alias="recipientTeamId", min_length=1)
    offered_athlete_ids: list[str] = Field(default_factory=list, alias="offeredAthleteIds")
    requested_athlete_ids: list[str] = Field(default_factory=list, alias="requestedAthleteIds")
    offered_credits: int = Field(default=0, alias="offeredCredits", ge=0, le=MAX_TRADE_CREDITS)
    requested_credits: int = Field(default=0, alias="requestedCredits", ge=0, le=MAX_TRADE_CREDITS)
    # Optional: omit or send null for a proposal that never expires on its own.
    expires_at: str | None = Field(default=None, alias="expiresAt")


class CounterTradeProposalRequest(ApiModel):
    """Same shape as a fresh proposal; the recipient becomes the new proposer."""

    offered_athlete_ids: list[str] = Field(default_factory=list, alias="offeredAthleteIds")
    requested_athlete_ids: list[str] = Field(default_factory=list, alias="requestedAthleteIds")
    offered_credits: int = Field(default=0, alias="offeredCredits", ge=0, le=MAX_TRADE_CREDITS)
    requested_credits: int = Field(default=0, alias="requestedCredits", ge=0, le=MAX_TRADE_CREDITS)
    expires_at: str | None = Field(default=None, alias="expiresAt")


class TradeAthleteResponse(ApiModel):
    id: str
    name: AthleteNameStr
    #: Valore di mercato in crediti di questa lega (budget della lega, almeno 1); ``None`` se il
    #: calciatore non è nel listone della stagione. Prezzo consigliato, non un minimo (1.3).
    market_value: int | None = Field(default=None, alias="marketValue")
    #: Media stagionale (in corso se ha almeno un voto, altrimenti la scorsa, es. «25/26»).
    season_average: AthleteSeasonAverageResponse | None = Field(default=None, alias="seasonAverage")


class TradeMissingRoleResponse(ApiModel):
    """Un ruolo da scegliere come sostituto e quanti (1.5)."""

    role: str
    count: int


class TradeReplacementCostResponse(ApiModel):
    """Quanto costano i sostituti di un ruolo che manca, ai prezzi dei liberi di adesso.

    Stesso prezzo dell'acquisto (il Valore, il minimo dove manca) e stessi liberi (non in rosa, non
    impegnati in aste o svincolati aperti).
    """

    role: str
    count: int
    #: Il libero più economico del ruolo; ``None`` se non c'è nessun libero.
    cheapest_price: int | None = Field(default=None, alias="cheapestPrice")
    #: I ``count`` liberi più economici insieme; ``None`` se non ce ne sono abbastanza.
    total_price: int | None = Field(default=None, alias="totalPrice")


class TradeRosterAfterResponse(ApiModel):
    """Come resterebbe la rosa di una squadra dopo lo scambio (1.5, avviso prima di accettare).

    ``missingRoles`` sono i sostituti che la squadra dovrà scegliere subito dagli svincolati, al
    loro Valore: vuoto se la rosa resta alla misura. Sito e app mostrano l'avviso da qui, senza
    calcolarlo da soli.

    Campi aggiunti dopo la corsa Mercato del 25/11 (solo avvisi, le app già installate li
    ignorano): i crediti dopo lo scambio, il prezzo più basso dei sostituti e se bastano, i ruoli
    che resterebbero sotto quota anche a rosa alla misura.
    """

    team_id: str = Field(alias="teamId")
    team_name: str = Field(alias="teamName")
    size_after: int = Field(alias="sizeAfter")
    roster_size: int = Field(alias="rosterSize")
    missing_roles: list[TradeMissingRoleResponse] = Field(
        default_factory=list, alias="missingRoles"
    )
    balance_after: int = Field(default=0, alias="balanceAfter")
    replacement_costs: list[TradeReplacementCostResponse] = Field(
        default_factory=list, alias="replacementCosts"
    )
    #: ``False`` se con i crediti di dopo lo scambio non potrà prendere da sola i sostituti
    #: (dovrà assegnarli l'admin). Lo scambio non si blocca: è solo un avviso.
    can_afford_replacement: bool = Field(default=True, alias="canAffordReplacement")
    #: Ruoli sotto la quota della lega subito dopo lo scambio (prima dei sostituti).
    under_quota_roles: list[RosterUnderQuotaRoleResponse] = Field(
        default_factory=list, alias="underQuotaRoles"
    )


class TradePreviewRequest(ApiModel):
    """Bozza di proposta (o controproposta) da valutare prima di inviarla."""

    recipient_team_id: str = Field(alias="recipientTeamId", min_length=1)
    offered_athlete_ids: list[str] = Field(default_factory=list, alias="offeredAthleteIds")
    requested_athlete_ids: list[str] = Field(default_factory=list, alias="requestedAthleteIds")
    # Facoltativi (le app 1.4 non li mandano): servono ai crediti dopo lo scambio.
    offered_credits: int = Field(default=0, alias="offeredCredits", ge=0, le=MAX_TRADE_CREDITS)
    requested_credits: int = Field(default=0, alias="requestedCredits", ge=0, le=MAX_TRADE_CREDITS)


class TradePreviewResponse(ApiModel):
    proposer_roster_after: TradeRosterAfterResponse = Field(alias="proposerRosterAfter")
    recipient_roster_after: TradeRosterAfterResponse = Field(alias="recipientRosterAfter")


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
    expires_at: str | None = Field(default=None, alias="expiresAt")
    created_at: str = Field(alias="createdAt")
    counter_of_id: str | None = Field(default=None, alias="counterOfId")
    # True se uno dei due saldi non copre i crediti della proposta: non si può accettare finché i
    # crediti non bastano (si riattiva da sola) e non conta nel limite delle proposte attive.
    awaiting_credits: bool = Field(default=False, alias="awaitingCredits")
    # Decaduta perché un calciatore non è più nella rosa attesa (non per data di scadenza).
    no_longer_valid: bool = Field(default=False, alias="noLongerValid")
    # 1.5: rosa delle due squadre dopo lo scambio, solo per le proposte ancora aperte (proposta o
    # in attesa dell'admin). Campi in più: le app già installate li ignorano.
    proposer_roster_after: TradeRosterAfterResponse | None = Field(
        default=None, alias="proposerRosterAfter"
    )
    recipient_roster_after: TradeRosterAfterResponse | None = Field(
        default=None, alias="recipientRosterAfter"
    )


class TradeProposalListResponse(ApiModel):
    proposals: list[TradeProposalResponse] = Field(default_factory=list)
