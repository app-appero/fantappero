"""Pannello operatore: import dello storico stagioni dal fornitore e ricalcolo del Valore (1.3).

Stesso schema dell'aggiornamento del listone (``admin.listone_service``): l'operatore chiede il
conto (``dryRun``, nessuna chiamata al fornitore), poi avvia il job Celery e ne segue
l'avanzamento (Redis, ``leagues.listone_refresh_progress`` con un ambito suo). Dopo l'import
si ricalcolano subito media stagionale e Valore.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from admin.season_history_schemas import (
    AdminMarketValuesRefreshResponse,
    AdminSeasonHistoryEstimateResponse,
    AdminSeasonHistoryImportResponse,
    AdminSeasonHistoryJobResponse,
    AdminSeasonHistoryProgressResponse,
    AdminSeasonHistoryResultResponse,
    AdminSeasonHistorySeasonEstimate,
)
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from config.settings.loader import get_api_settings
from leagues.listone_refresh_progress import (
    ListoneRefreshProgress,
    load_active_job_id,
    load_progress,
    new_job_id,
    save_progress,
)
from market.valuation_service import MarketValuesRefreshResult, refresh_market_values
from observability.logging import get_logger
from sports_data.provider.client import ApiFootballClient, build_client_from_settings
from sports_data.provider.errors import (
    PROVIDER_RATE_LIMITED_USER_MESSAGE,
    PROVIDER_UNAVAILABLE_USER_MESSAGE,
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
)
from sports_data.provider.throttle import DEFAULT_REQUESTS_PER_MINUTE
from sports_data.season_stats.provider_import import (
    STOP_MAX_CALLS,
    STOP_QUOTA_RESERVE,
    STOP_TOO_MANY_ERRORS,
    ImportEstimate,
    estimate_import,
    run_provider_import,
)

#: Ambito del puntatore «job attivo» (non si mescola con l'aggiornamento del listone).
SEASON_HISTORY_JOB_SCOPE = "season-history"

_logger = get_logger(__name__)

_STOP_MESSAGES = {
    STOP_MAX_CALLS: "Fermato al tetto di chiamate: rilancia l'import per continuare.",
    STOP_QUOTA_RESERVE: (
        "Fermato per lasciare quota ai giri live: rilancia l'import domani per continuare."
    ),
    STOP_TOO_MANY_ERRORS: ("Fermato dopo troppi errori di fila del fornitore: riprova più tardi."),
}


def _requests_per_minute(settings: Any) -> int:
    value = getattr(settings, "api_football_requests_per_minute", DEFAULT_REQUESTS_PER_MINUTE)
    try:
        return max(1, int(value or DEFAULT_REQUESTS_PER_MINUTE))
    except (TypeError, ValueError):
        return DEFAULT_REQUESTS_PER_MINUTE


def estimate_response(
    estimate: ImportEstimate, *, requests_per_minute: int
) -> AdminSeasonHistoryEstimateResponse:
    calls = estimate.estimated_calls
    return AdminSeasonHistoryEstimateResponse(
        seasonYear=estimate.current_season_year,
        seasons=[
            AdminSeasonHistorySeasonEstimate(
                seasonYear=item.season_year,
                seasonLabel=item.label,
                leaguePagesDone=item.league_pages_done,
                leaguePagesRemaining=item.league_pages_remaining,
                leaguePagesExact=item.league_pages_exact,
                listoneAthletes=item.listone_athletes,
                athletesWithRows=item.athletes_with_rows,
                athletesChecked=item.athletes_checked,
                athletesToFill=item.athletes_to_fill,
                athletesToFillExact=item.athletes_to_fill_exact,
                rowsStored=item.rows_stored,
                estimatedCalls=item.estimated_calls,
            )
            for item in estimate.seasons
        ],
        estimatedCalls=calls,
        estimatedMinutes=math.ceil(calls / requests_per_minute) if calls else 0,
        requestsPerMinute=requests_per_minute,
    )


def market_values_response(result: MarketValuesRefreshResult) -> AdminMarketValuesRefreshResponse:
    return AdminMarketValuesRefreshResponse(
        seasonYear=result.season_year,
        skipped=result.skipped,
        currentSeasonRows=result.current_season_rows,
        athletesValued=result.athletes_valued,
        athletesWithHistory=result.athletes_with_history,
        athletesWithCurrentAverage=result.athletes_with_current_average,
        athletesWithPreviousAverage=result.athletes_with_previous_average,
        computedAt=result.computed_at,
    )


def import_season_history(
    session: Session,
    *,
    season_year: int,
    max_calls: int,
    client: ApiFootballClient | None = None,
    on_progress: Callable[[int, str, str], None] | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> AdminSeasonHistoryResultResponse:
    """Scarica le stagioni passate mancanti, poi ricalcola media stagionale e Valore."""
    owns_client = client is None
    settings = get_api_settings()

    def report(percent: int, stage: str, message: str) -> None:
        if on_progress is not None:
            on_progress(max(0, min(100, percent)), stage, message)

    try:
        if client is None:
            try:
                client = build_client_from_settings(settings)
            except ProviderConfigError as exc:
                raise ValidationAuthError(
                    PROVIDER_UNAVAILABLE_USER_MESSAGE,
                    code="provider_key_missing",
                ) from exc

        def import_progress(done: int, planned: int, label: str) -> None:
            ratio = min(1.0, done / planned) if planned else 1.0
            report(2 + int(ratio * 90), "provider", f"{label} ({done} chiamate)")

        report(2, "provider", "Import dello storico avviato…")
        run = run_provider_import(
            session,
            client,
            current_season_year=season_year,
            max_calls=max_calls,
            on_progress=import_progress,
            checkpoint=checkpoint,
        )
        report(93, "market_values", "Ricalcolo di medie e Valore…")
        values = refresh_market_values(session, season_year=season_year, force=True)
        remaining = estimate_import(session, current_season_year=season_year)
        counters = run.counters
        message = (
            "Storico importato. Medie e Valore ricalcolati."
            if run.completed
            else _STOP_MESSAGES.get(run.stopped_reason or "", "Import fermato prima della fine.")
        )
        return AdminSeasonHistoryResultResponse(
            seasonYear=season_year,
            seasons=list(run.seasons),
            calls=counters.calls,
            leaguePages=counters.league_pages,
            athletesChecked=counters.athletes_checked,
            athletesFound=counters.athletes_found,
            rowsCreated=counters.rows_created,
            rowsUpdated=counters.rows_updated,
            snapshotsCreated=counters.snapshots_created,
            errors=counters.errors,
            stoppedReason=run.stopped_reason,
            message=message,
            marketValues=market_values_response(values),
            remaining=estimate_response(
                remaining, requests_per_minute=_requests_per_minute(settings)
            ),
        )
    except ValidationAuthError:
        raise
    except ProviderRateLimitError as exc:
        raise ValidationAuthError(
            PROVIDER_RATE_LIMITED_USER_MESSAGE, code="provider_rate_limited"
        ) from exc
    except ProviderAuthError as exc:
        raise ValidationAuthError(
            PROVIDER_UNAVAILABLE_USER_MESSAGE, code="provider_auth_failed"
        ) from exc
    except ProviderError as exc:
        _logger.exception("season_history_import_failed", extra={"season_year": season_year})
        raise ValidationAuthError(
            "Import dello storico non riuscito dal provider sportivo.",
            code="provider_sync_failed",
        ) from exc
    finally:
        if owns_client and client is not None:
            client.close()


class AdminSeasonHistoryService:
    """Conto, avvio e avanzamento dell'import; ricalcolo del Valore a richiesta."""

    def __init__(self, session: Session, settings: Any) -> None:
        self._session = session
        self._settings = settings

    def estimate(self, *, season_year: int) -> AdminSeasonHistoryEstimateResponse:
        return estimate_response(
            estimate_import(self._session, current_season_year=season_year),
            requests_per_minute=_requests_per_minute(self._settings),
        )

    def start_import(
        self,
        *,
        season_year: int,
        dry_run: bool,
        max_calls: int,
        actor: User,
    ) -> AdminSeasonHistoryImportResponse:
        estimate = self.estimate(season_year=season_year)
        if dry_run:
            return AdminSeasonHistoryImportResponse(dryRun=True, estimate=estimate, job=None)
        active = self.get_active_progress()
        if active is not None and active.status in ("queued", "running"):
            return AdminSeasonHistoryImportResponse(
                dryRun=False,
                estimate=estimate,
                job=AdminSeasonHistoryJobResponse(
                    jobId=active.job_id,
                    status=active.status,
                    message="Un import dello storico è già in corso.",
                ),
            )
        from admin.season_history_tasks import import_season_history_task

        job_id = new_job_id()
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=SEASON_HISTORY_JOB_SCOPE,
                status="queued",
                percent=0,
                stage="queued",
                message="Import dello storico in coda…",
            )
        )
        import_season_history_task.delay(
            job_id=job_id,
            season_year=season_year,
            max_calls=max_calls,
            actor_id=str(actor.id),
        )
        return AdminSeasonHistoryImportResponse(
            dryRun=False,
            estimate=estimate,
            job=AdminSeasonHistoryJobResponse(
                jobId=job_id,
                status="queued",
                message="Import dello storico avviato.",
            ),
        )

    def get_progress(self, *, job_id: str) -> AdminSeasonHistoryProgressResponse:
        progress = load_progress(job_id)
        if progress is None or progress.league_id != SEASON_HISTORY_JOB_SCOPE:
            raise ValidationAuthError(
                "Job di import dello storico non trovato.",
                code="season_history_job_not_found",
            )
        return self._to_progress_response(progress)

    def get_active_progress(self) -> AdminSeasonHistoryProgressResponse | None:
        job_id = load_active_job_id(SEASON_HISTORY_JOB_SCOPE)
        if job_id is None:
            return None
        progress = load_progress(job_id)
        if progress is None:
            return None
        return self._to_progress_response(progress)

    def refresh_market_values(
        self, *, season_year: int, force: bool
    ) -> AdminMarketValuesRefreshResponse:
        result = refresh_market_values(self._session, season_year=season_year, force=force)
        self._session.commit()
        return market_values_response(result)

    @staticmethod
    def _to_progress_response(
        progress: ListoneRefreshProgress,
    ) -> AdminSeasonHistoryProgressResponse:
        result = None
        if progress.result is not None:
            result = AdminSeasonHistoryResultResponse.model_validate(progress.result)
        return AdminSeasonHistoryProgressResponse(
            jobId=progress.job_id,
            status=progress.status,
            percent=progress.percent,
            stage=progress.stage,
            message=progress.message,
            errorCode=progress.error_code,
            result=result,
        )
