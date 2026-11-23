"""Schemi HTTP del pannello operatore: storico stagioni dal fornitore e Valore (1.3)."""

from __future__ import annotations

from datetime import datetime

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
