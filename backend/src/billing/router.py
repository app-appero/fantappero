"""HTTP routes for entitlements and the subscription webhook (EP11-01/02)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from auth.models.user import User
from authorization.dependencies import require_permissions
from billing.entitlement_service import EntitlementService
from billing.schemas import (
    EntitlementStatusResponse,
    SubscriptionWebhookRequest,
    SubscriptionWebhookResponse,
)
from billing.webhook_service import process_payment_event
from config.settings.api import ApiSettings
from config.settings.loader import get_api_settings
from database.enums import Permission

router = APIRouter(tags=["billing"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "code": exc.code},
    )


@router.get("/billing/me", response_model=EntitlementStatusResponse)
def get_my_entitlement(
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    session: Session = Depends(get_db_session),
) -> EntitlementStatusResponse:
    status_row = EntitlementService(session).get_status(current_user.id)
    return EntitlementStatusResponse(
        plan=status_row.plan.value,
        activeUntil=status_row.active_until.isoformat() if status_row.active_until else None,
        aiDailyLimit=status_row.ai_daily_limit,
    )


@router.post("/billing/webhook", response_model=SubscriptionWebhookResponse)
def receive_subscription_webhook(
    body: SubscriptionWebhookRequest,
    x_webhook_secret: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> SubscriptionWebhookResponse | JSONResponse:
    if x_webhook_secret != settings.billing_webhook_secret:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Firma webhook non valida.", "code": "invalid_webhook_signature"},
        )
    try:
        user_id = UUID(body.user_id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Identificativo utente non valido.", "code": "invalid_user_id"},
        )
    try:
        payment, _created = process_payment_event(
            session,
            external_event_id=body.event_id,
            user_id=user_id,
            plan_code=body.plan_code,
        )
    except AuthError as exc:
        return _error_response(exc)
    session.commit()
    return SubscriptionWebhookResponse(
        paymentId=str(payment.id), planCode=payment.plan_code, processed=True
    )
