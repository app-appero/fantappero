"""HTTP routes for european fantasy turns (EP06-01)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from authorization.context import LeagueAccess
from authorization.dependencies import require_league_permissions
from database.enums import Permission
from fantasy_turns.calendar_refresh_progress import load_progress, new_job_id, save_progress
from fantasy_turns.calendar_refresh_progress import CalendarRefreshProgress
from fantasy_turns.live_service import get_fixture_live_detail
from fantasy_turns.schemas import (
    EnsureFantasyTurnsResponse,
    ExcludeFantasyTurnFixtureRequest,
    FantasyCalendarRefreshJobResponse,
    FantasyCalendarRefreshProgressResponse,
    FantasyCalendarRefreshResultResponse,
    FantasyTurnDetailResponse,
    FantasyTurnPreviewResponse,
    FantasyTurnSummaryResponse,
    FixtureLiveDetailResponse,
    GenerateFantasyTurnRequest,
    PendingFixtureResponse,
    RoundCalculationResponse,
)
from fantasy_turns.service import FantasyTurnService

router = APIRouter(prefix="/leagues", tags=["fantasy-turns"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "code": exc.code},
    )


def get_fantasy_turn_service(
    session: Session = Depends(get_db_session),
) -> FantasyTurnService:
    return FantasyTurnService(session)


@router.get("/{league_id}/turni", response_model=list[FantasyTurnSummaryResponse])
def list_fantasy_turns(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MATCHDAY_VIEW)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> list[FantasyTurnSummaryResponse]:
    """Elenco turni europei della lega."""
    return service.list_turns(league_access)


@router.get("/{league_id}/turni/{round_id}", response_model=FantasyTurnDetailResponse)
def get_fantasy_turn(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MATCHDAY_VIEW)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> FantasyTurnDetailResponse | JSONResponse:
    """Dettaglio turno con fixture, cutoff e stato effettivo."""
    try:
        return service.get_turn(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/turni/{round_id}/partite/{fixture_id}",
    response_model=FixtureLiveDetailResponse,
)
def get_fantasy_turn_fixture(
    round_id: UUID,
    fixture_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MATCHDAY_VIEW)),
    session: Session = Depends(get_db_session),
) -> FixtureLiveDetailResponse | JSONResponse:
    """Dettaglio partita: risultato, formazioni ufficiali e cronologia (EP13-P04)."""
    try:
        return get_fixture_live_detail(
            session,
            league_id=league_access.league.id,
            round_id=round_id,
            fixture_id=fixture_id,
        )
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/turni/sincronizza",
    response_model=EnsureFantasyTurnsResponse,
)
def ensure_fantasy_turns(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> EnsureFantasyTurnsResponse | JSONResponse:
    """Assicura i turni upcoming dai campionati della lega (idempotente)."""
    from config.settings.loader import get_api_settings

    settings = get_api_settings()
    try:
        return service.ensure_upcoming_for_league_access(
            league_access,
            horizon_days=settings.fantasy_turns_horizon_days,
            auto_open=True,
        )
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/turni/da-aggiornare",
    response_model=list[PendingFixtureResponse],
)
def list_pending_fixtures(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MATCHDAY_VIEW)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> list[PendingFixtureResponse]:
    """Fixture note ma senza data/ora dal provider: non appartengono ancora a nessun turno."""
    return service.list_pending_fixtures(league_access)


@router.post(
    "/{league_id}/turni/aggiorna-calendario",
    response_model=FantasyCalendarRefreshJobResponse,
)
def start_calendar_refresh(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.GLOBAL_OPERATE)),
) -> FantasyCalendarRefreshJobResponse:
    """Avvia il comando unico "Aggiorna calendario" (sync provider + backfill stagionale).

    Solo operatore di piattaforma (EP-turni-automazione): il refresh gira già
    da solo ogni 6 ore per tutte le leghe attive, questo endpoint resta
    l'override manuale puntuale per una singola lega.
    """
    from fantasy_turns.tasks import refresh_full_calendar_task

    job_id = new_job_id()
    league_id = str(league_access.league.id)
    save_progress(
        CalendarRefreshProgress(
            job_id=job_id,
            league_id=league_id,
            status="queued",
            percent=0,
            stage="queued",
            message="Aggiornamento calendario in coda…",
        )
    )
    refresh_full_calendar_task.delay(
        job_id=job_id,
        league_id=league_id,
        actor_id=str(league_access.user.id),
    )
    return FantasyCalendarRefreshJobResponse(
        jobId=job_id,
        status="queued",
        message="Aggiornamento calendario avviato.",
    )


@router.get(
    "/{league_id}/turni/aggiorna-calendario/{job_id}",
    response_model=FantasyCalendarRefreshProgressResponse,
)
def get_calendar_refresh_progress(
    job_id: str,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.GLOBAL_OPERATE)),
) -> FantasyCalendarRefreshProgressResponse | JSONResponse:
    progress = load_progress(job_id)
    if progress is None or progress.league_id != str(league_access.league.id):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Job di aggiornamento non trovato.", "code": "calendar_refresh_job_not_found"},
        )
    result = None
    if progress.result is not None:
        result = FantasyCalendarRefreshResultResponse.model_validate(progress.result)
    return FantasyCalendarRefreshProgressResponse(
        jobId=progress.job_id,
        status=progress.status,
        percent=progress.percent,
        stage=progress.stage,
        message=progress.message,
        errorCode=progress.error_code,
        result=result,
    )


@router.post(
    "/{league_id}/turni/anteprima",
    response_model=FantasyTurnPreviewResponse,
)
def preview_fantasy_turn(
    body: GenerateFantasyTurnRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> FantasyTurnPreviewResponse | JSONResponse:
    """Anteprima generazione turno senza persistenza."""
    try:
        return service.preview(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/turni",
    response_model=FantasyTurnDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_fantasy_turn(
    body: GenerateFantasyTurnRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> FantasyTurnDetailResponse | JSONResponse:
    """Genera manualmente un turno europeo (scheduled o skipped)."""
    try:
        return service.generate(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post("/{league_id}/turni/{round_id}/apri", response_model=FantasyTurnDetailResponse)
def open_fantasy_turn(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.GLOBAL_OPERATE)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> FantasyTurnDetailResponse | JSONResponse:
    """Apre un turno programmato (scheduled → open).

    Solo operatore di piattaforma (EP-turni-automazione): l'apertura è
    ormai automatica alla omologazione del turno precedente, questo resta
    l'override manuale per i casi eccezionali.
    """
    try:
        return service.open_turn(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/turni/{round_id}/escludi-fixture",
    response_model=FantasyTurnDetailResponse,
)
def exclude_fantasy_turn_fixture(
    round_id: UUID,
    body: ExcludeFantasyTurnFixtureRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> FantasyTurnDetailResponse | JSONResponse:
    """Esclude una partita dal turno (solo prima dell'apertura)."""
    try:
        return service.exclude_fixture(league_access, round_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/turni/{round_id}/ricalcola-cutoff",
    response_model=FantasyTurnDetailResponse,
)
def recalculate_fantasy_turn_cutoff(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.GLOBAL_OPERATE)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> FantasyTurnDetailResponse | JSONResponse:
    """Ricalcola cutoff e stato effettivo dagli orari fixture correnti.

    Solo operatore di piattaforma (EP-turni-automazione).
    """
    try:
        return service.recalculate_cutoff(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/turni/{round_id}/calcola-giornata",
    response_model=RoundCalculationResponse,
)
def calculate_fantasy_round(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.GLOBAL_OPERATE)),
    service: FantasyTurnService = Depends(get_fantasy_turn_service),
) -> RoundCalculationResponse | JSONResponse:
    """Forza il calcolo della giornata: stessa logica del job automatico (EP-turni-calcolo).

    Solo operatore di piattaforma. Verifica formazioni (con fallback per
    quelle mancanti), calcola punteggi fantasy e risultati H2H, aggiorna la
    classifica, e omologa il turno se i dati sono definitivi.
    """
    try:
        return service.calculate_round(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)
