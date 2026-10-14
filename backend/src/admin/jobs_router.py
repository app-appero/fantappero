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
from system_jobs.service import list_jobs, update_job

router = APIRouter(prefix="/admin", tags=["admin"])


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
