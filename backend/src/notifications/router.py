"""HTTP routes for the in-app notification center (EP09-01)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from auth.models.user import User
from authorization.dependencies import require_permissions
from database.enums import NotificationCategory, Permission
from notifications.schemas import (
    MarkAllReadResponse,
    NotificationItemResponse,
    NotificationListResponse,
    NotificationPreferenceListResponse,
    UpdateNotificationPreferenceRequest,
)
from notifications.service import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _error_response(exc: AuthError) -> JSONResponse:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "notification_not_found":
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )


def get_notification_service(session: Session = Depends(get_db_session)) -> NotificationService:
    return NotificationService(session)


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    category: NotificationCategory | None = Query(default=None),
    unread_only: bool = Query(default=False, alias="unreadOnly"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    return service.list_notifications(
        user_id=current_user.id,
        category=category,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )


@router.post("/{notification_id}/read", response_model=NotificationItemResponse)
def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationItemResponse | JSONResponse:
    try:
        return service.mark_read(user_id=current_user.id, notification_id=notification_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post("/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: NotificationService = Depends(get_notification_service),
) -> MarkAllReadResponse:
    return service.mark_all_read(user_id=current_user.id)


@router.get("/preferences", response_model=NotificationPreferenceListResponse)
def get_notification_preferences(
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationPreferenceListResponse:
    return service.get_preferences(user_id=current_user.id)


@router.put("/preferences", response_model=NotificationPreferenceListResponse)
def update_notification_preference(
    body: UpdateNotificationPreferenceRequest,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationPreferenceListResponse | JSONResponse:
    try:
        category = NotificationCategory(body.category)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Categoria non valida.", "code": "invalid_category"},
        )
    service.update_preference(
        user_id=current_user.id,
        category=category,
        in_app_enabled=body.in_app_enabled,
    )
    return service.get_preferences(user_id=current_user.id)
