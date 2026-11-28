"""Pannello operatore — turni, calendario, formazioni IA (EP-turni-automazione).

Azioni massive (tutte le leghe attive) + lettura di supporto. Le azioni
puntuali (una lega/turno specifico) restano sugli endpoint già esistenti in
`fantasy_turns.router`/`fantasy_lineups.router`, ora protetti da
`Permission.GLOBAL_OPERATE` invece che `LEAGUE_ADMIN` — non duplicati qui.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from admin.schemas import (
    AdminAiLineupsSyncResultResponse,
    AdminCalendarSyncJobResponse,
    AdminCalendarSyncProgressResponse,
    AdminCalendarSyncResultResponse,
    AdminHistoricalRepairJobResponse,
    AdminHistoricalRepairProgressResponse,
    AdminHistoricalRepairRequest,
    AdminHistoricalRepairResultResponse,
    AdminLeagueTurnStatusResponse,
    AdminPredictedHintDiagnosisResponse,
    AdminResultRecoveryJobResponse,
    AdminResultRecoveryProgressResponse,
    AdminResultRecoveryResultResponse,
    AdminRoundCalculationResultResponse,
    AdminSeasonImportJobResponse,
    AdminSeasonImportProgressResponse,
    AdminSeasonImportResultResponse,
    AdminTurniBatchOperationResponse,
    AdminTurniBatchResponse,
    AdminTurniSyncResultResponse,
)
from admin.turni_batch import (
    AUDIT_OPERATION_BATCH,
    BATCH_OPERATIONS,
    BatchProgress,
    BatchUnavailableError,
    acquire_lock,
    new_batch_id,
    new_progress,
    release_lock,
)
from admin.turni_batch import (
    load_progress as load_batch_progress,
)
from admin.turni_batch import (
    save_progress as save_batch_progress,
)
from admin.turni_service import list_league_turn_status
from auth.dependencies import get_db_session
from auth.models.user import User
from authorization.dependencies import require_permissions
from database.enums import LeagueAuditAction, Permission
from fantasy_turns.calendar_refresh_progress import (
    CalendarRefreshProgress,
    load_progress,
    new_job_id,
    save_progress,
)
from fantasy_turns.schemas import PredictedLineupSyncResponse
from fantasy_turns.service import FantasyTurnService
from leagues.models.league_audit_event import LeagueAuditEvent
from observability.logging import get_logger

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)

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


@router.post("/turni/probabili-formazioni", response_model=PredictedLineupSyncResponse)
def refresh_predicted_lineups(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> PredictedLineupSyncResponse:
    """Scarica subito le formazioni probabili delle partite non iniziate.

    Stessa primitiva del cron giornaliero, per tutte le leghe, anche se uno
    snapshot è recente e anche se il job automatico è spento.
    """
    from sports_data.predicted.tasks import run_predicted_lineup_sync

    payload = run_predicted_lineup_sync(force=True, manual=True)
    return PredictedLineupSyncResponse(
        fixturesConsidered=int(payload.get("fixtures_considered") or 0),
        matchesLinked=int(payload.get("matches_linked") or 0),
        snapshotsSaved=int(payload.get("snapshots_saved") or 0),
        skippedRecent=int(payload.get("skipped_recent") or 0),
        skippedUnmatched=int(payload.get("skipped_unmatched") or 0),
        rejected=int(payload.get("rejected") or 0),
        warnings=int(payload.get("warnings") or 0),
        requestsMade=int(payload.get("requests_made") or 0),
        message=payload.get("message") if isinstance(payload.get("message"), str) else None,
    )


@router.get(
    "/turni/probabili-formazioni/diagnosi",
    response_model=list[AdminPredictedHintDiagnosisResponse],
)
def diagnose_predicted_lineup_hints(
    fantasyTeamId: UUID,
    roundId: UUID,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> list[AdminPredictedHintDiagnosisResponse]:
    """Per ogni giocatore in rosa, perché ha (o non ha) un indizio di formazione
    probabile: nessuna fixture collegata al turno, nessuno snapshot ancora
    scaricato, snapshot scartato per affidabilità, o non abbinato dal provider.

    Diagnostica, non usata dalla formazione vera e propria: query più ampie di
    ``hints_for_fixtures``, apposta per spiegare un buco, non per servirlo veloce.
    """
    from fantasy_teams.models import FantasyTeam
    from sports_data.predicted.read import diagnose_hints

    team = session.get(FantasyTeam, fantasyTeamId)
    if team is None:
        raise HTTPException(status_code=404, detail="Squadra non trovata.")
    athlete_ids = [slot.athlete_id for slot in team.slots if slot.athlete_id is not None]
    diagnoses = diagnose_hints(session, roundId, athlete_ids)
    return [
        AdminPredictedHintDiagnosisResponse(
            athleteId=str(diagnosis.athlete_id),
            athleteName=diagnosis.athlete_name,
            clubName=diagnosis.club_name,
            fixtureId=None if diagnosis.fixture_id is None else str(diagnosis.fixture_id),
            hint=diagnosis.hint,
            reason=diagnosis.reason,
            detail=diagnosis.detail,
            similarUnmatchedNames=list(diagnosis.similar_unmatched_names),
        )
        for diagnosis in diagnoses
    ]


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


@router.post("/calendario/importa-stagione", response_model=AdminSeasonImportJobResponse)
def start_season_import(
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminSeasonImportJobResponse:
    """Importa subito catalogo + calendario fixture per tutti i campionati MVP.

    Indipendente da qualunque lega: pensato per l'inizio stagione, prima
    ancora che esista una lega — così creazione lega e "Genera calendario"
    trovano sempre i dati già pronti nel DB invece di chiamare il provider
    inline. Stessa coppia di sync che gira già in automatico via cron
    (`sports_data.sync_mvp_catalog` / `sync_mvp_fixtures`), qui come
    override manuale puntuale.
    """
    from sports_data.season_import_tasks import PLATFORM_SCOPE, import_season_task

    job_id = new_job_id()
    save_progress(
        CalendarRefreshProgress(
            job_id=job_id,
            league_id=PLATFORM_SCOPE,
            status="queued",
            percent=0,
            stage="queued",
            message="Importazione calendario stagione in coda…",
        )
    )
    import_season_task.delay(job_id=job_id, actor_id=str(operator.id))
    return AdminSeasonImportJobResponse(
        jobId=job_id,
        status="queued",
        message="Importazione calendario stagione avviata.",
    )


@router.get(
    "/calendario/importa-stagione/{job_id}",
    response_model=AdminSeasonImportProgressResponse,
)
def get_season_import_progress(
    job_id: str,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminSeasonImportProgressResponse | JSONResponse:
    from sports_data.season_import_tasks import PLATFORM_SCOPE

    progress = load_progress(job_id)
    if progress is None or progress.league_id != PLATFORM_SCOPE:
        return JSONResponse(
            status_code=404,
            content={
                "message": "Job di importazione non trovato.",
                "code": "season_import_job_not_found",
            },
        )
    result = None
    if progress.result is not None:
        result = AdminSeasonImportResultResponse.model_validate(progress.result)
    return AdminSeasonImportProgressResponse(
        jobId=progress.job_id,
        status=progress.status,
        percent=progress.percent,
        stage=progress.stage,
        message=progress.message,
        errorCode=progress.error_code,
        result=result,
    )


@router.post("/turni/recupera-risultati", response_model=AdminResultRecoveryJobResponse)
def start_stale_result_recovery(
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminResultRecoveryJobResponse:
    """Forza il recupero dei risultati arretrati e il calcolo dei turni.

    Per la giornata rimasta «in programma» a partita già giocata: risincronizza
    gli stati di tutti i campionati, scarica le statistiche mancanti, omologa
    i turni pronti e apre il successivo se il cutoff non è passato.
    """
    from fantasy_turns.tasks import recover_stale_results_task

    job_id = new_job_id()
    save_progress(
        CalendarRefreshProgress(
            job_id=job_id,
            league_id=_PLATFORM_SCOPE,
            status="queued",
            percent=0,
            stage="queued",
            message="Recupero risultati in coda…",
        )
    )
    recover_stale_results_task.delay(job_id=job_id, actor_id=str(operator.id))
    return AdminResultRecoveryJobResponse(
        jobId=job_id,
        status="queued",
        message="Recupero risultati avviato.",
    )


@router.get(
    "/turni/recupera-risultati/{job_id}",
    response_model=AdminResultRecoveryProgressResponse,
)
def get_stale_result_recovery_progress(
    job_id: str,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminResultRecoveryProgressResponse | JSONResponse:
    progress = load_progress(job_id)
    if progress is None or progress.league_id != _PLATFORM_SCOPE:
        return JSONResponse(
            status_code=404,
            content={
                "message": "Job di recupero non trovato.",
                "code": "result_recovery_job_not_found",
            },
        )
    result = None
    if progress.result is not None:
        result = AdminResultRecoveryResultResponse.model_validate(progress.result)
    return AdminResultRecoveryProgressResponse(
        jobId=progress.job_id,
        status=progress.status,
        percent=progress.percent,
        stage=progress.stage,
        message=progress.message,
        errorCode=progress.error_code,
        result=result,
    )


@router.post("/turni/calcola-giornata", response_model=AdminRoundCalculationResultResponse)
def calculate_current_rounds_all_leagues(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> AdminRoundCalculationResultResponse:
    """Calcola la giornata corrente per tutte le leghe attive.

    Sincrono, come "Sincronizza turni": solo lavoro DB locale, stessa
    selezione turni del job automatico (`process_live_fantasy_rounds`),
    stesso motore di calcolo dei comandi puntuali (EP-turni-calcolo).
    """
    from fantasy_turns.live_pipeline import process_live_fantasy_rounds

    result = process_live_fantasy_rounds(session)
    session.commit()
    return AdminRoundCalculationResultResponse.model_validate(result.as_dict())


@router.post("/turni/ricalcola-storico", response_model=AdminHistoricalRepairJobResponse)
def start_historical_repair(
    body: AdminHistoricalRepairRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminHistoricalRepairJobResponse:
    """Riapre e ricalcola i turni con un buco storico (formazioni mai
    risolte, scontri H2H mai chiusi) su tutte le leghe attive.

    Azione distinta dal calcolo di routine: può riaprire turni già
    omologati (con motivo obbligatorio) e inviare notifiche di correzione
    agli utenti — async con progress, come "Aggiorna calendario".
    """
    from fantasy_turns.round_calculation_progress import RoundRepairProgress
    from fantasy_turns.round_calculation_progress import save_progress as save_repair_progress
    from fantasy_turns.tasks import repair_historical_rounds_task

    job_id = new_job_id()
    save_repair_progress(
        RoundRepairProgress(
            job_id=job_id,
            league_id=_PLATFORM_SCOPE,
            status="queued",
            percent=0,
            stage="queued",
            message="Ricalcolo storico in coda…",
        )
    )
    repair_historical_rounds_task.delay(
        job_id=job_id,
        actor_id=str(operator.id),
        reason=body.reason,
    )
    return AdminHistoricalRepairJobResponse(
        jobId=job_id,
        status="queued",
        message="Ricalcolo storico avviato per tutte le leghe attive.",
    )


@router.get(
    "/turni/ricalcola-storico/{job_id}",
    response_model=AdminHistoricalRepairProgressResponse,
)
def get_historical_repair_progress(
    job_id: str,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminHistoricalRepairProgressResponse | JSONResponse:
    from fantasy_turns.round_calculation_progress import load_progress as load_repair_progress

    progress = load_repair_progress(job_id)
    if progress is None or progress.league_id != _PLATFORM_SCOPE:
        return JSONResponse(
            status_code=404,
            content={
                "message": "Job di ricalcolo storico non trovato.",
                "code": "round_repair_job_not_found",
            },
        )
    result = None
    if progress.result is not None:
        result = AdminHistoricalRepairResultResponse.model_validate(progress.result)
    return AdminHistoricalRepairProgressResponse(
        jobId=progress.job_id,
        status=progress.status,
        percent=progress.percent,
        stage=progress.stage,
        message=progress.message,
        errorCode=progress.error_code,
        result=result,
    )


def _batch_response(progress: BatchProgress) -> AdminTurniBatchResponse:
    return AdminTurniBatchResponse(
        batchId=progress.batch_id,
        status=progress.status,
        operations=[
            AdminTurniBatchOperationResponse(
                key=operation.key,
                label=operation.label,
                status=operation.status,
                message=operation.message,
            )
            for operation in progress.operations
        ],
        ok=progress.count("ok"),
        failed=progress.count("failed"),
        skipped=progress.count("skipped"),
        startedAt=progress.started_at,
        finishedAt=progress.finished_at,
    )


@router.post("/turni/esegui-tutti", response_model=AdminTurniBatchResponse)
def start_turni_batch(
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> AdminTurniBatchResponse | JSONResponse:
    """«Esegui tutti»: lancia in sequenza le operazioni dei turni che si possono rilanciare.

    Importa calendario stagione, Genera calendario, Sincronizza turni, Aggiorna probabili e Genera
    formazioni IA, una dopo l'altra in un task del worker; un errore non ferma le altre. Restano
    fuori omologazioni, «Ricalcola storico» e le azioni per singola lega. Un solo blocco alla
    volta (409 se ce n'è già uno in corso); l'avanzamento si legge dal GET con lo stesso id.
    """
    batch_id = new_batch_id()
    try:
        acquired = acquire_lock(batch_id)
    except BatchUnavailableError:
        return JSONResponse(
            status_code=503,
            content={
                "message": (
                    "Non riesco a controllare se le operazioni sono già in corso "
                    "(Redis non risponde). Riprova tra poco."
                ),
                "code": "turni_batch_lock_unavailable",
            },
        )
    if not acquired:
        return JSONResponse(
            status_code=409,
            content={
                "message": (
                    "Le operazioni dei turni sono già in corso: aspetta che finiscano "
                    "prima di rilanciarle."
                ),
                "code": "turni_batch_already_running",
            },
        )
    progress = new_progress(batch_id, str(operator.id))
    save_batch_progress(progress)
    session.add(
        LeagueAuditEvent(
            league_id=None,
            actor_id=operator.id,
            action=LeagueAuditAction.SYSTEM_JOB_RUN_MANUAL,
            details={
                "operation": AUDIT_OPERATION_BATCH,
                "batchId": batch_id,
                "operations": [spec.key for spec in BATCH_OPERATIONS],
            },
        )
    )
    session.commit()
    logger.info(
        f"turni_batch_started batch_id={batch_id} actor_id={operator.id}",
        extra={"batch_id": batch_id, "actor_id": str(operator.id)},
    )
    from admin.turni_batch_tasks import run_turni_batch_task

    try:
        run_turni_batch_task.apply_async(
            kwargs={"batch_id": batch_id, "actor_id": str(operator.id)},
            task_id=batch_id,
        )
    except Exception:  # noqa: BLE001 — il broker o il worker non rispondono
        logger.exception(f"turni_batch_dispatch_failed batch_id={batch_id}")
        release_lock(batch_id)
        return JSONResponse(
            status_code=502,
            content={
                "message": (
                    "Non riesco a mettere in coda le operazioni dei turni. Riprova tra poco."
                ),
                "code": "turni_batch_dispatch_failed",
            },
        )
    return _batch_response(load_batch_progress(batch_id) or progress)


@router.get("/turni/esegui-tutti/{batch_id}", response_model=AdminTurniBatchResponse)
def get_turni_batch_progress(
    batch_id: str,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
) -> AdminTurniBatchResponse | JSONResponse:
    progress = load_batch_progress(batch_id)
    if progress is None:
        return JSONResponse(
            status_code=404,
            content={
                "message": "Blocco di operazioni non trovato (o scaduto).",
                "code": "turni_batch_not_found",
            },
        )
    return _batch_response(progress)
