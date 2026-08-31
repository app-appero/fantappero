"""Pannello operatore — turni, calendario, formazioni IA (EP-turni-automazione).

Azioni massive (tutte le leghe attive) + lettura di supporto. Le azioni
puntuali (una lega/turno specifico) restano sugli endpoint già esistenti in
`fantasy_turns.router`/`fantasy_lineups.router`, ora protetti da
`Permission.GLOBAL_OPERATE` invece che `LEAGUE_ADMIN` — non duplicati qui.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from admin.schemas import (
    AdminAiLineupsSyncResultResponse,
    AdminCalendarSyncJobResponse,
    AdminCalendarSyncProgressResponse,
    AdminCalendarSyncResultResponse,
    AdminLeagueTurnStatusResponse,
    AdminTurniSyncResultResponse,
)
from admin.turni_service import list_league_turn_status
from auth.dependencies import get_db_session
from auth.models.user import User
from authorization.dependencies import require_permissions
from database.enums import Permission
from fantasy_turns.calendar_refresh_progress import (
    CalendarRefreshProgress,
    load_progress,
    new_job_id,
    save_progress,
)
from fantasy_turns.service import FantasyTurnService

router = APIRouter(prefix="/admin", tags=["admin"])

_PLATFORM_SCOPE = "platform"


@router.get("/turni/leghe", response_model=list[AdminLeagueTurnStatusResponse])
def list_leagues_turn_status(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> list[AdminLeagueTurnStatusResponse]:
    """Leghe attive con turno corrente/stato/omologazione, per decidere se
    serve un'azione puntuale prima (o invece) del massivo."""
    return list_league_turn_status(session)


@router.post("/turni/sincronizza", response_model=AdminTurniSyncResultResponse)
def sync_all_league_turns(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> AdminTurniSyncResultResponse:
    """Apre i turni pronti e ricalcola i cutoff per tutte le leghe attive.

    Stessa primitiva del cron orario `fantasy_turns.ensure_upcoming`, on-demand.
    """
    totals = FantasyTurnService(session).ensure_upcoming_for_active_leagues()
    session.commit()
    return AdminTurniSyncResultResponse.model_validate(totals)


@router.post("/formazioni-ia/genera", response_model=AdminAiLineupsSyncResultResponse)
def generate_all_ai_lineups(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> AdminAiLineupsSyncResultResponse:
    """Schiera le squadre IA di tutti i turni aperti/programmati, tutte le
    leghe attive. Stessa primitiva del cron `fantasy_lineups.generate_ai`,
    on-demand."""
    from fantasy_lineups.ai_service import generate_ai_lineups_for_active_leagues

    result = generate_ai_lineups_for_active_leagues(session)
    session.commit()
    return AdminAiLineupsSyncResultResponse.model_validate(result)


@router.post("/calendario/sincronizza", response_model=AdminCalendarSyncJobResponse)
def start_calendar_sync_all_leagues(
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminCalendarSyncJobResponse:
    """Avvia "Aggiorna calendario" per tutte le leghe attive in un colpo.

    Async con progress (come il refresh puntuale): itera potenzialmente
    molte leghe, ognuna con una chiamata al provider esterno.
    """
    from fantasy_turns.tasks import refresh_full_calendar_active_leagues_now_task

    job_id = new_job_id()
    save_progress(
        CalendarRefreshProgress(
            job_id=job_id,
            league_id=_PLATFORM_SCOPE,
            status="queued",
            percent=0,
            stage="queued",
            message="Aggiornamento calendario massivo in coda…",
        )
    )
    refresh_full_calendar_active_leagues_now_task.delay(
        job_id=job_id,
        actor_id=str(operator.id),
    )
    return AdminCalendarSyncJobResponse(
        jobId=job_id,
        status="queued",
        message="Aggiornamento calendario avviato per tutte le leghe attive.",
    )


@router.get(
    "/calendario/sincronizza/{job_id}",
    response_model=AdminCalendarSyncProgressResponse,
)
def get_calendar_sync_all_leagues_progress(
    job_id: str,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminCalendarSyncProgressResponse | JSONResponse:
    progress = load_progress(job_id)
    if progress is None or progress.league_id != _PLATFORM_SCOPE:
        return JSONResponse(
            status_code=404,
            content={
                "message": "Job di aggiornamento non trovato.",
                "code": "calendar_refresh_job_not_found",
            },
        )
    result = None
    if progress.result is not None:
        result = AdminCalendarSyncResultResponse.model_validate(progress.result)
    return AdminCalendarSyncProgressResponse(
        jobId=progress.job_id,
        status=progress.status,
        percent=progress.percent,
        stage=progress.stage,
        message=progress.message,
        errorCode=progress.error_code,
        result=result,
    )
