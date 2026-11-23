"""Schemi HTTP del pannello operatore: storico stagioni dal fornitore e Valore (1.3), dettaglio
del Valore di un calciatore (1.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from auth.schemas import ApiModel


class AdminSeasonHistoryImportRequest(ApiModel):
    """«Importa lo storico» (``POST /admin/listone/storico``)."""

    #: Stagione in corso del listone (2026 per la 2026/27): si importano le due precedenti.
    season_year: int = Field(alias="seasonYear", ge=2000, le=2100)
    #: ``true`` (default): solo il conto delle chiamate, nessuna chiamata al fornitore.
    dry_run: bool = Field(default=True, alias="dryRun")
    #: Tetto di chiamate di questa esecuzione; si riprende rilanciando.
    max_calls: int = Field(default=2000, alias="maxCalls", ge=1, le=20_000)


class AdminSeasonHistorySeasonEstimate(ApiModel):
    season_year: int = Field(alias="seasonYear")
    season_label: str = Field(alias="seasonLabel")
    league_pages_done: int = Field(alias="leaguePagesDone")
    league_pages_remaining: int = Field(alias="leaguePagesRemaining")
    #: ``false`` finché la prima pagina di qualche campionato non dice quante sono.
    league_pages_exact: bool = Field(alias="leaguePagesExact")
    listone_athletes: int = Field(alias="listoneAthletes")
    athletes_with_rows: int = Field(alias="athletesWithRows")
    athletes_checked: int = Field(alias="athletesChecked")
    athletes_to_fill: int = Field(alias="athletesToFill")
    #: ``false`` finché mancano pagine di campionato (il conto è una stima).
    athletes_to_fill_exact: bool = Field(alias="athletesToFillExact")
    rows_stored: int = Field(alias="rowsStored")
    estimated_calls: int = Field(alias="estimatedCalls")


class AdminSeasonHistoryEstimateResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    seasons: list[AdminSeasonHistorySeasonEstimate]
    estimated_calls: int = Field(alias="estimatedCalls")
    #: Minuti stimati al ritmo del client (chiamate al minuto delle impostazioni).
    estimated_minutes: int = Field(alias="estimatedMinutes")
    requests_per_minute: int = Field(alias="requestsPerMinute")


class AdminSeasonHistoryJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class AdminSeasonHistoryImportResponse(ApiModel):
    dry_run: bool = Field(alias="dryRun")
    estimate: AdminSeasonHistoryEstimateResponse
    #: Il job avviato (o quello già in corso); ``null`` in modalità conta.
    job: AdminSeasonHistoryJobResponse | None = None


class AdminMarketValuesRefreshRequest(ApiModel):
    season_year: int = Field(alias="seasonYear", ge=2000, le=2100)
    #: Ricalcola anche se voti e storico non sono cambiati dall'ultima volta.
    force: bool = True


class AdminMarketValuesRefreshResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    skipped: bool
    current_season_rows: int = Field(alias="currentSeasonRows")
    athletes_valued: int = Field(alias="athletesValued")
    athletes_with_history: int = Field(alias="athletesWithHistory")
    athletes_with_current_average: int = Field(alias="athletesWithCurrentAverage")
    athletes_with_previous_average: int = Field(alias="athletesWithPreviousAverage")
    computed_at: datetime | None = Field(default=None, alias="computedAt")


class AdminSeasonHistoryResultResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    seasons: list[int]
    calls: int
    league_pages: int = Field(alias="leaguePages")
    athletes_checked: int = Field(alias="athletesChecked")
    athletes_found: int = Field(alias="athletesFound")
    rows_created: int = Field(alias="rowsCreated")
    rows_updated: int = Field(alias="rowsUpdated")
    snapshots_created: int = Field(alias="snapshotsCreated")
    errors: int
    #: ``null`` se finito; ``max_calls`` / ``quota_reserve`` / ``too_many_errors`` se fermato
    #: prima (si riprende rilanciando l'import: salta quello che c'è già).
    stopped_reason: str | None = Field(default=None, alias="stoppedReason")
    message: str
    market_values: AdminMarketValuesRefreshResponse | None = Field(
        default=None, alias="marketValues"
    )
    #: Quello che resta da scaricare dopo questa esecuzione.
    remaining: AdminSeasonHistoryEstimateResponse | None = None


class AdminSeasonHistoryProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: AdminSeasonHistoryResultResponse | None = None


# --- «Dettaglio del Valore» di un calciatore (1.4) ---------------------------------------------


class AdminMarketValueSeasonRow(ApiModel):
    """Una riga dello storico letta per il Valore (calciatore + club + competizione)."""

    competition: str
    club: str | None = None
    #: Peso nella media: presenze (fornitore) o partite con voto (FantApperò).
    appearances: int
    average: float | None = None
    #: ``league`` (contata); ``cup``, ``unknown`` (non campionato) e ``no_rating`` (senza
    #: media) sono escluse.
    kind: Literal["league", "cup", "unknown", "no_rating"]


class AdminMarketValueSeasonDetail(ApiModel):
    """Una delle tre stagioni del Valore: da dove vengono i numeri e quanto pesa."""

    slot: Literal["current", "previous", "twoSeasonsAgo"]
    season_year: int = Field(alias="seasonYear")
    season_label: str = Field(alias="seasonLabel")
    is_current: bool = Field(alias="isCurrent")
    #: Fonte delle righe usate: ``provider`` (fornitore) o ``fantappero``; ``null`` senza righe.
    source: Literal["provider", "fantappero"] | None = None
    #: Competizioni contate (nomi), dalla più giocata.
    competitions: list[str]
    rows: list[AdminMarketValueSeasonRow]
    #: Righe escluse (coppe, tipo sconosciuto, senza media).
    excluded: list[AdminMarketValueSeasonRow]
    #: ``false`` = stagione senza dati: vale ``missingSeasonIndex`` (in corso: peso 0).
    has_data: bool = Field(alias="hasData")
    #: Presenze con voto (n).
    appearances: int
    average: float | None = None
    role_average: float | None = Field(default=None, alias="roleAverage")
    shrunk_average: float | None = Field(default=None, alias="shrunkAverage")
    percentile: float | None = None
    #: Posizione nel ruolo (1 = media ristretta più alta) e calciatori del ruolo con dati.
    rank: int | None = None
    pool_size: int | None = Field(default=None, alias="poolSize")
    weight: float
    #: Indice che entra nella somma: il percentile, o quello di una stagione senza dati.
    index_used: float = Field(alias="indexUsed")
    #: ``weight × indexUsed``.
    contribution: float


class AdminMarketValueLeagueCredits(ApiModel):
    league_id: str = Field(alias="leagueId")
    league_name: str = Field(alias="leagueName")
    budget: int
    credits: int


class AdminMarketValueDetailResponse(ApiModel):
    """``GET /admin/listone/valori/{athleteId}``: come si arriva al Valore di un calciatore."""

    athlete_id: str = Field(alias="athleteId")
    canonical_name: str = Field(alias="canonicalName")
    club_name: str | None = Field(default=None, alias="clubName")
    role: Literal["P", "D", "C", "A"]
    season_year: int = Field(alias="seasonYear")
    season_label: str = Field(alias="seasonLabel")
    #: ``computed``: dettaglio completo; ``outdated``: riga scritta prima della 1.4 (solo
    #: percentili e pesi: ricalcolare i valori); ``not_computed``: nessuna riga, vale il valore
    #: base del ruolo fino al prossimo ricalcolo.
    status: Literal["computed", "outdated", "not_computed"]
    #: Versione della formula con cui è stata scritta la riga.
    version: str | None = None
    computed_at: datetime | None = Field(default=None, alias="computedAt")
    #: Indice combinato p (0..1).
    value_index: float = Field(alias="valueIndex")
    #: Crediti per il budget di riferimento, non arrotondati.
    reference_value: float = Field(alias="referenceValue")
    #: Crediti al budget di riferimento, arrotondati (almeno 1).
    reference_credits: int = Field(alias="referenceCredits")
    reference_budget: int = Field(alias="referenceBudget")
    role_top: float = Field(alias="roleTop")
    floor: float
    curve_exponent: float = Field(alias="curveExponent")
    missing_season_index: float = Field(alias="missingSeasonIndex")
    shrink_appearances: int = Field(alias="shrinkAppearances")
    current_full_weight_appearances: int = Field(alias="currentFullWeightAppearances")
    #: Valore (crediti di riferimento) di chi non ha storico, nello stesso ruolo.
    base_reference_value: float = Field(alias="baseReferenceValue")
    #: Dalla stagione in corso alla più vecchia.
    seasons: list[AdminMarketValueSeasonDetail]
    #: Crediti al budget della lega (solo con ``leagueId``).
    league: AdminMarketValueLeagueCredits | None = None
