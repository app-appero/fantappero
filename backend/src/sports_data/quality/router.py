"""API operatore per il pannello qualità dati sportivi (EP04-07)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.models.user import User
from authorization.dependencies import require_permissions
from database.enums import Permission
from sports_data.quality.retry import QualityRetryError
from sports_data.quality.schemas import (
    QualityIssueResponse,
    QualityScanRequest,
    QualityScanResponse,
    QualitySummaryResponse,
    SyncRetryRequest,
    SyncRetryResponse,
)
from sports_data.quality.service import SportsDataQualityService
from sports_data.quality.types import QualityIssueStatus

router = APIRouter(prefix="/sports-data/quality", tags=["sports-data-quality"])


def get_quality_service(session: Session = Depends(get_db_session)) -> SportsDataQualityService:
    return SportsDataQualityService(session)


@router.get("/summary", response_model=QualitySummaryResponse)
def get_quality_summary(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: SportsDataQualityService = Depends(get_quality_service),
) -> QualitySummaryResponse:
    """Riepilogo issue di qualità (solo operatore globale)."""
    return service.summary()


@router.get("/issues", response_model=list[QualityIssueResponse])
def list_quality_issues(
    kind: str | None = Query(default=None),
    status: str | None = Query(default=QualityIssueStatus.OPEN.value),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: SportsDataQualityService = Depends(get_quality_service),
) -> list[QualityIssueResponse]:
    """Elenco issue: mancanti, ritardi, conflitti, correzioni."""
    return service.list_issues(kind=kind, status=status, limit=limit, offset=offset)


@router.post("/scan", response_model=QualityScanResponse)
def run_quality_scan(
    body: QualityScanRequest | None = None,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: SportsDataQualityService = Depends(get_quality_service),
) -> QualityScanResponse:
    """Esegue uno scan qualità (idempotente) e aggiorna le issue aperte."""
    request = body or QualityScanRequest()
    return service.run_scan(fixture_id=request.fixture_id)


@router.post("/issues/{issue_id}/retry-sync", response_model=SyncRetryResponse)
def retry_sync_for_issue(
    issue_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: SportsDataQualityService = Depends(get_quality_service),
) -> SyncRetryResponse:
    """Rilancia la sync della fixture collegata all’issue (auditata, senza edit manuali)."""
    return service.request_retry_for_issue(issue_id=issue_id, operator=operator)


@router.post("/retry-sync", response_model=SyncRetryResponse)
def retry_sync_for_fixture(
    body: SyncRetryRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: SportsDataQualityService = Depends(get_quality_service),
) -> SyncRetryResponse:
    """Rilancia la sync per ``fixtureProviderId`` esplicito."""
    if body.fixture_provider_id is None:
        raise QualityRetryError(
            "fixture_provider_required",
            "Campo fixtureProviderId obbligatorio per il rilancio sync",
        )
    return service.request_retry_for_fixture(
        fixture_provider_id=body.fixture_provider_id,
        operator=operator,
    )


@router.get("/retries", response_model=list[SyncRetryResponse])
def list_sync_retries(
    limit: int = Query(default=50, ge=1, le=200),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: SportsDataQualityService = Depends(get_quality_service),
) -> list[SyncRetryResponse]:
    return service.list_retries(limit=limit)


@router.get("/retries/{retry_id}", response_model=SyncRetryResponse)
def get_sync_retry(
    retry_id: UUID,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: SportsDataQualityService = Depends(get_quality_service),
) -> SyncRetryResponse:
    return service.get_retry(retry_id)


def quality_error_handler(_request: object, exc: QualityRetryError) -> JSONResponse:
    status_code = 404 if exc.code.endswith("not_found") else 400
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )
