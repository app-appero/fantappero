"""Admin panel HTTP routes — platform operator only (EP11-04a)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from admin.exceptions import AdminError
from admin.listone_service import AdminListoneService
from admin.schemas import (
    AdminListoneEntryResponse,
    AdminListoneRefreshJobResponse,
    AdminListoneRefreshProgressResponse,
    AdminOverviewResponse,
    AdminUserResponse,
    PaginatedAdminLeaguesResponse,
    PaginatedAdminUsersResponse,
)
from admin.service import AdminService
from auth.dependencies import get_db_session
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.dependencies import require_permissions
from config.settings.api import ApiSettings
from config.settings.loader import get_api_settings
from database.enums import Permission

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> AdminService:
    return AdminService(session, settings)


def get_admin_listone_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> AdminListoneService:
    return AdminListoneService(session, settings)


def _error_response(exc: AdminError) -> JSONResponse:
    status_code = 404 if exc.code == "admin_user_not_found" else 409
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


@router.get("/leagues", response_model=PaginatedAdminLeaguesResponse)
def list_leagues(
    query: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: AdminService = Depends(get_admin_service),
) -> PaginatedAdminLeaguesResponse:
    return service.list_leagues(query=query, page=page)


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
