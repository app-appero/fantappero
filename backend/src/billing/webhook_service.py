"""Idempotent subscription-payment webhook processing (EP11-02).

No real payment provider is integrated (no provider key/SDK exists in this
environment — nothing to configure without inventing a secret). The webhook
shape (external event id, user id, plan code) and the idempotency/activation
logic are real and provider-agnostic; swapping in a real provider later only
means replacing how the payload is authenticated and parsed, not this logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from billing.entitlement_service import EntitlementService
from billing.models import SubscriptionPayment

# EUR cents. "3,99 €/mese" / "29,99 €/stagione" per Doc §11.
PLAN_PRICING: dict[str, tuple[int, timedelta]] = {
    "monthly": (399, timedelta(days=30)),
    "seasonal": (2999, timedelta(days=270)),
}


class InvalidPlanCodeError(ValidationAuthError):
    def __init__(self) -> None:
        super().__init__("Codice piano non valido.", code="invalid_plan_code")


def process_payment_event(
    session: Session,
    *,
    external_event_id: str,
    user_id: UUID,
    plan_code: str,
) -> tuple[SubscriptionPayment, bool]:
    """Record a payment event and extend the user's PRO entitlement.

    Returns ``(payment, created)``. Replaying the same ``external_event_id``
    is idempotent: it returns the original row and does not re-activate.
    """
    existing = session.scalar(
        select(SubscriptionPayment).where(
            SubscriptionPayment.external_event_id == external_event_id
        )
    )
    if existing is not None:
        return existing, False

    if plan_code not in PLAN_PRICING:
        raise InvalidPlanCodeError()
    amount_cents, duration = PLAN_PRICING[plan_code]

    payment = SubscriptionPayment(
        user_id=user_id,
        plan_code=plan_code,
        amount_cents=amount_cents,
        external_event_id=external_event_id,
    )
    try:
        with session.begin_nested():
            session.add(payment)
            session.flush()
    except IntegrityError:
        replayed = session.scalar(
            select(SubscriptionPayment).where(
                SubscriptionPayment.external_event_id == external_event_id
            )
        )
        if replayed is not None:
            return replayed, False
        raise

    now = datetime.now(UTC)
    entitlements = EntitlementService(session)
    current = entitlements.get_status(user_id, now=now)
    base = current.active_until if current.active_until and current.active_until > now else now
    entitlements.activate_pro_until(user_id, until=base + duration)

    return payment, True
