"""HTTP routes for the in-app notification center (EP09-01)."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from auth.models.user import User
from authorization.dependencies import require_permissions
from database.enums import NotificationCategory, Permission
from notifications.event_catalog import EVENT_KEYS
from notifications.samples import SAMPLES
from notifications.schemas import (
    MarkAllReadResponse,
    NotificationItemResponse,
    NotificationListResponse,
    NotificationPreferenceListResponse,
    PushDeviceResponse,
    RegisterPushDeviceRequest,
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


@router.post("/test-samples", response_model=MarkAllReadResponse)
def send_test_samples(
    current_user: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: NotificationService = Depends(get_notification_service),
) -> MarkAllReadResponse:
    """Crea per l'operatore un esempio di ogni tipo di notifica (anche push), per provarle."""
    batch = uuid4()
    created = 0
    for sample in SAMPLES:
        _, was_created = service.create_notification(
            user_id=current_user.id,
            category=sample.category,
            template_key=sample.template_key,
            template_version=sample.template_version,
            params=sample.params,
            dedup_key=f"test-sample:{batch}:{sample.key}",
        )
        created += 1 if was_created else 0
    return MarkAllReadResponse(marked_count=created)


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
    """Due forme nello stesso corpo (TASK5): per categoria (compatibilità,
    EP09-01) o granulare per evento, selezionate da quale campo è presente.
    """
    if body.event_key is not None:
        if body.category is not None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": "Non si possono aggiornare categoria ed evento insieme.",
                    "code": "invalid_preference_request",
                },
            )
        if body.event_key not in EVENT_KEYS:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Evento non valido.", "code": "invalid_event_key"},
            )
        if body.in_app_enabled is None and body.push_enabled is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": "Specifica almeno un canale da aggiornare.",
                    "code": "invalid_preference_request",
                },
            )
        service.update_event_preference(
            user_id=current_user.id,
            event_key=body.event_key,
            in_app_enabled=body.in_app_enabled,
            push_enabled=body.push_enabled,
        )
        return service.get_preferences(user_id=current_user.id)

    if body.category is None or body.in_app_enabled is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": "Specifica una categoria e lo stato in-app.",
                "code": "invalid_preference_request",
            },
        )
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


@router.post("/push-devices", response_model=PushDeviceResponse)
def register_push_device(
    body: RegisterPushDeviceRequest,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: NotificationService = Depends(get_notification_service),
) -> PushDeviceResponse:
    """Registra (o sposta su questo utente) il token Expo del dispositivo."""
    return service.register_push_device(
        user_id=current_user.id,
        token=body.token,
        platform=body.platform,
    )


@router.delete(
    "/push-devices/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def unregister_push_device(
    token: str,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    service: NotificationService = Depends(get_notification_service),
) -> Response:
    service.unregister_push_device(user_id=current_user.id, token=token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
