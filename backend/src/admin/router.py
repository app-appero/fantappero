"""Admin panel HTTP routes — platform operator only (EP11-04a)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from admin.exceptions import AdminError
from admin.listone_service import AdminListoneService
from admin.schemas import (
    AdminAddBlockedRequest,
    AdminAddTesterRequest,
    AdminBlocklistResponse,
    AdminDeleteUserRequest,
    AdminDeleteUserResponse,
    AdminImpersonateResponse,
    AdminImpersonationRevokeResponse,
    AdminListoneEntryResponse,
    AdminListoneRefreshJobResponse,
    AdminListoneRefreshProgressResponse,
    AdminOverviewResponse,
    AdminTestModeResponse,
    AdminTestModeUpdateRequest,
    AdminTransferReviewedResponse,
    AdminUserResponse,
    PaginatedAdminLeaguesResponse,
    PaginatedAdminPendingTransfersResponse,
    PaginatedAdminUsersResponse,
)
from admin.service import AdminService
from admin.transfers_service import AdminTransfersService
from auth.dependencies import get_db_session, get_impersonation_store
from auth.exceptions import AuthError, ValidationAuthError
from auth.impersonation import ImpersonationStore
from auth.models.user import User
from authorization.dependencies import require_permissions
from config.settings.api import ApiSettings
from config.settings.loader import get_api_settings
from database.enums import Permission

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
    impersonation_store: ImpersonationStore | None = Depends(get_impersonation_store),
) -> AdminService:
    return AdminService(session, settings, impersonation_store)


def get_admin_listone_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> AdminListoneService:
    return AdminListoneService(session, settings)


def get_admin_transfers_service(
    session: Session = Depends(get_db_session),
) -> AdminTransfersService:
    return AdminTransfersService(session)


_NOT_FOUND_CODES = frozenset({"admin_user_not_found", "admin_transfer_not_found"})


def _error_response(exc: AdminError) -> JSONResponse:
    status_code = 404 if exc.code in _NOT_FOUND_CODES else 409
    return JSONResponse(status_code=status_code, content={"message": exc.message, "code": exc.code})


def _listone_error_response(exc: ValidationAuthError) -> JSONResponse:
    status_code = 404 if exc.code == "listone_refresh_job_not_found" else 400
    return JSONResponse(status_code=status_code, content={"message": exc.message, "code": exc.code})


@router.get("/overview", response_model=AdminOverviewResponse)
def get_overview(
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminOverviewResponse:
    return service.overview(operator)


@router.get("/users", response_model=PaginatedAdminUsersResponse)
def list_users(
    query: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> PaginatedAdminUsersResponse:
    return service.list_users(query=query, page=page)


@router.get("/test-mode", response_model=AdminTestModeResponse)
def get_test_mode(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminTestModeResponse:
    """Stato della modalità test (accesso solo ai tester) e lista dei tester."""
    return service.test_mode_state()


@router.put("/test-mode", response_model=AdminTestModeResponse)
def set_test_mode(
    body: AdminTestModeUpdateRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminTestModeResponse:
    return service.set_test_mode(actor=operator, enabled=body.enabled)


@router.post("/test-mode/testers", response_model=AdminTestModeResponse)
def add_tester(
    body: AdminAddTesterRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminTestModeResponse | JSONResponse:
    try:
        return service.add_tester(actor=operator, email=body.email)
    except AuthError as exc:
        return JSONResponse(status_code=400, content={"message": exc.message, "code": exc.code})


@router.delete("/test-mode/testers/{tester_id}", response_model=AdminTestModeResponse)
def remove_tester(
    tester_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminTestModeResponse | JSONResponse:
    try:
        return service.remove_tester(actor=operator, tester_id=tester_id)
    except AuthError as exc:
        return JSONResponse(status_code=404, content={"message": exc.message, "code": exc.code})


@router.post("/users/{user_id}/delete", response_model=AdminDeleteUserResponse)
def delete_user(
    user_id: UUID,
    body: AdminDeleteUserRequest | None = None,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminDeleteUserResponse | JSONResponse:
    """Elimina l'utente (dati personali rimossi); con `block` ne blocca anche l'email."""
    try:
        return service.delete_user(
            actor=operator, target_user_id=user_id, block=body.block if body else True
        )
    except AdminError as exc:
        return _error_response(exc)
    except AuthError as exc:
        return JSONResponse(status_code=400, content={"message": exc.message, "code": exc.code})


@router.get("/blocklist", response_model=AdminBlocklistResponse)
def get_blocklist(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminBlocklistResponse:
    return service.blocklist()


@router.post("/blocklist", response_model=AdminBlocklistResponse)
def add_blocked(
    body: AdminAddBlockedRequest,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminBlocklistResponse | JSONResponse:
    try:
        return service.add_blocked(actor=operator, email=body.email, reason=body.reason)
    except AdminError as exc:
        return _error_response(exc)
    except AuthError as exc:
        return JSONResponse(status_code=400, content={"message": exc.message, "code": exc.code})


@router.delete("/blocklist/{entry_id}", response_model=AdminBlocklistResponse)
def remove_blocked(
    entry_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminBlocklistResponse | JSONResponse:
    try:
        return service.remove_blocked(actor=operator, entry_id=entry_id)
    except AuthError as exc:
        return JSONResponse(status_code=404, content={"message": exc.message, "code": exc.code})


@router.post("/users/{user_id}/promote", response_model=AdminUserResponse)
def promote_user(
    user_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminUserResponse | JSONResponse:
    try:
        return service.promote_operator(actor=operator, target_user_id=user_id)
    except AdminError as exc:
        return _error_response(exc)


@router.post("/users/{user_id}/revoke", response_model=AdminUserResponse)
def revoke_user(
    user_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminUserResponse | JSONResponse:
    try:
        return service.revoke_operator(actor=operator, target_user_id=user_id)
    except AdminError as exc:
        return _error_response(exc)


@router.post("/users/{user_id}/impersonate", response_model=AdminImpersonateResponse)
def impersonate_user(
    user_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminImpersonateResponse | JSONResponse:
    try:
        return service.impersonate(actor=operator, target_user_id=user_id)
    except AdminError as exc:
        return _error_response(exc)


@router.post("/users/{user_id}/impersonate/revoke", response_model=AdminImpersonationRevokeResponse)
def revoke_impersonation(
    user_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> AdminImpersonationRevokeResponse | JSONResponse:
    try:
        return service.revoke_impersonation(actor=operator, target_user_id=user_id)
    except AdminError as exc:
        return _error_response(exc)


@router.get("/leagues", response_model=PaginatedAdminLeaguesResponse)
def list_leagues(
    query: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> PaginatedAdminLeaguesResponse:
    return service.list_leagues(query=query, page=page)


@router.get("/transfers/pending-review", response_model=PaginatedAdminPendingTransfersResponse)
def list_pending_transfers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminTransfersService = Depends(get_admin_transfers_service),
) -> PaginatedAdminPendingTransfersResponse:
    """Trasferimenti Loan/N.D. non chiudibili in automatico (OQ-12)."""
    return service.list_pending_review(page=page, page_size=page_size)


@router.post("/transfers/{transfer_id}/review", response_model=AdminTransferReviewedResponse)
def review_transfer(
    transfer_id: UUID,
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminTransfersService = Depends(get_admin_transfers_service),
) -> AdminTransferReviewedResponse | JSONResponse:
    try:
        return service.mark_reviewed(actor=operator, transfer_id=transfer_id)
    except AdminError as exc:
        return _error_response(exc)


@router.get("/listone", response_model=list[AdminListoneEntryResponse])
def list_listone(
    season_year: int = Query(alias="seasonYear", ge=2000, le=2100),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminListoneService = Depends(get_admin_listone_service),
) -> list[AdminListoneEntryResponse]:
    return service.list_entries(season_year=season_year)


@router.post("/listone/aggiorna", response_model=AdminListoneRefreshJobResponse)
def start_listone_refresh(
    season_year: int = Query(alias="seasonYear", ge=2000, le=2100),
    operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminListoneService = Depends(get_admin_listone_service),
) -> AdminListoneRefreshJobResponse:
    return service.start_refresh_job(season_year=season_year, actor=operator)


@router.get("/listone/aggiorna", response_model=AdminListoneRefreshProgressResponse | None)
def get_active_listone_refresh(
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminListoneService = Depends(get_admin_listone_service),
) -> AdminListoneRefreshProgressResponse | None:
    """Lets any operator discover a refresh already in progress, not just the
    one who started it (EP11-05)."""
    return service.get_active_refresh_progress()


@router.get("/listone/aggiorna/{job_id}", response_model=AdminListoneRefreshProgressResponse)
def get_listone_refresh_progress(
    job_id: str,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminListoneService = Depends(get_admin_listone_service),
) -> AdminListoneRefreshProgressResponse | JSONResponse:
    try:
        return service.get_refresh_progress(job_id=job_id)
    except ValidationAuthError as exc:
        return _listone_error_response(exc)
