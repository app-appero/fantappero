"""Pannello operatore — job periodici del sistema."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from auth.schemas import ApiModel
from authorization.dependencies import require_permissions
from database.enums import Permission
from system_jobs.manual import (
    CODE_ALREADY_RUNNING,
    CODE_DISPATCH_FAILED,
    CODE_LOCK_UNAVAILABLE,
    STATUS_ALREADY_RUNNING,
    STATUS_FAILED,
    STATUS_STARTED,
    ManualRunResult,
    launch_all_enabled,
    launch_job,
)
from system_jobs.service import list_jobs, update_job

router = APIRouter(prefix="/admin", tags=["admin"])


class SystemJobLastRunResponse(ApiModel):
    outcome: str
    finished_at: datetime = Field(alias="finishedAt")
    reason: str | None = None


class SystemJobResponse(ApiModel):
    key: str
    title: str
    description: str
    task: str
    enabled: bool
    interval_seconds: int = Field(alias="intervalSeconds")
    min_interval_seconds: int = Field(alias="minIntervalSeconds")
    max_interval_seconds: int = Field(alias="maxIntervalSeconds")
    last_started_at: datetime | None = Field(alias="lastStartedAt")
    next_run_at: datetime | None = Field(alias="nextRunAt")
    #: Il giro chiama il fornitore sportivo: consuma la sua quota (avviso in «Esegui»).
    uses_provider_quota: bool = Field(default=False, alias="usesProviderQuota")
    #: Il giro può mandare avvisi ai fantallenatori.
    sends_notifications: bool = Field(default=False, alias="sendsNotifications")
    #: Sta girando adesso (lancio a mano o giro del beat).
    running: bool = False
    last_run: SystemJobLastRunResponse | None = Field(default=None, alias="lastRun")


class SystemJobRunResultResponse(ApiModel):
    """Esito del lancio a mano di un job: il giro è in coda, non ancora finito."""

    key: str
    title: str
    status: str  # started | already_running | failed
    message: str
    warning: str | None = None
    code: str | None = None
    task_id: str | None = Field(default=None, alias="taskId")


class SystemJobRunAllResponse(ApiModel):
    results: list[SystemJobRunResultResponse]
    started: int
    already_running: int = Field(alias="alreadyRunning")
    failed: int


class SystemJobUpdateRequest(ApiModel):
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, alias="intervalSeconds")


@router.get("/job", response_model=list[SystemJobResponse])
def get_system_jobs(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> list[SystemJobResponse]:
    """Job che partono da soli: stato, frequenza e prossima esecuzione."""
    views = list_jobs(session)
    session.commit()
    return [SystemJobResponse.model_validate(view.as_dict()) for view in views]


@router.patch("/job/{job_key}", response_model=SystemJobResponse)
def patch_system_job(
    job_key: str,
    body: SystemJobUpdateRequest,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> SystemJobResponse | JSONResponse:
    """Accende, spegne o cambia la frequenza di un job periodico."""
    try:
        view = update_job(
            session,
            job_key,
            enabled=body.enabled,
            interval_seconds=body.interval_seconds,
        )
    except ValidationAuthError as exc:
        status = 404 if exc.code == "system_job_not_found" else 422
        return JSONResponse(status_code=status, content={"message": exc.message, "code": exc.code})
    session.commit()
    return SystemJobResponse.model_validate(view.as_dict())


_RUN_ERROR_STATUS = {
    CODE_ALREADY_RUNNING: 409,
    CODE_LOCK_UNAVAILABLE: 503,
    CODE_DISPATCH_FAILED: 502,
}


def _run_result_response(result: ManualRunResult) -> SystemJobRunResultResponse:
    return SystemJobRunResultResponse.model_validate(result.as_dict())


@router.post("/job/esegui-tutti", response_model=SystemJobRunAllResponse)
def run_all_system_jobs(
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> SystemJobRunAllResponse:
    """«Esegui tutti»: manda al worker tutti i job accesi, uno dopo l'altro.

    Un job già in esecuzione non si rilancia e uno che non parte non ferma gli altri: l'esito è
    per job. I job spenti non si toccano (si lanciano a mano uno alla volta).
    """
    results = launch_all_enabled(session, actor_id=operator.id)
    session.commit()
    return SystemJobRunAllResponse(
        results=[_run_result_response(result) for result in results],
        started=sum(1 for result in results if result.status == STATUS_STARTED),
        alreadyRunning=sum(1 for result in results if result.status == STATUS_ALREADY_RUNNING),
        failed=sum(1 for result in results if result.status == STATUS_FAILED),
    )


@router.post("/job/{job_key}/esegui", response_model=SystemJobRunResultResponse)
def run_system_job(
    job_key: str,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> SystemJobRunResultResponse | JSONResponse:
    """«Esegui»: lancia a mano un job, anche se è spento (con un avviso).

    Manda al worker lo stesso task del beat, non cambia frequenza né orari. 409 se il job sta già
    girando.
    """
    try:
        result = launch_job(session, job_key, actor_id=operator.id)
    except ValidationAuthError as exc:
        return JSONResponse(status_code=404, content={"message": exc.message, "code": exc.code})
    session.commit()
    if result.status != STATUS_STARTED:
        return JSONResponse(
            status_code=_RUN_ERROR_STATUS.get(result.code or "", 500),
            content={"message": result.message, "code": result.code},
        )
    return _run_result_response(result)
