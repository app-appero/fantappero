"""Integration tests for entitlements and the subscription webhook (EP11-01/02)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from billing.entitlement_service import EntitlementService
from billing.models import UserEntitlement
from billing.webhook_service import process_payment_event
from config.settings.loader import get_api_settings
from database.enums import SubscriptionPlan
from mail.capture import get_captured_emails


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


def test_default_plan_is_free_with_base_ai_limit(client: TestClient, db_session: Session) -> None:
    _, user_id = _register_and_login(client, "billing-default@example.com")
    status_row = EntitlementService(db_session).get_status(user_id)
    assert status_row.plan == SubscriptionPlan.FREE
    assert status_row.active_until is None
    assert status_row.ai_daily_limit == 20


def test_webhook_activates_pro_and_replay_is_idempotent(
    client: TestClient, db_session: Session
) -> None:
    token, user_id = _register_and_login(client, "billing-webhook@example.com")
    settings = get_api_settings()
    event_id = str(uuid4())

    first = client.post(
        "/billing/webhook",
        headers={"X-Webhook-Secret": settings.billing_webhook_secret},
        json={"eventId": event_id, "userId": str(user_id), "planCode": "monthly"},
    )
    assert first.status_code == 200
    payment_id = first.json()["paymentId"]

    status_row = EntitlementService(db_session).get_status(user_id)
    assert status_row.plan == SubscriptionPlan.PRO
    assert status_row.ai_daily_limit == 100

    # Replaying the same provider event must not double-activate or duplicate the payment.
    second = client.post(
        "/billing/webhook",
        headers={"X-Webhook-Secret": settings.billing_webhook_secret},
        json={"eventId": event_id, "userId": str(user_id), "planCode": "monthly"},
    )
    assert second.status_code == 200
    assert second.json()["paymentId"] == payment_id


def test_webhook_rejects_invalid_secret(client: TestClient) -> None:
    response = client.post(
        "/billing/webhook",
        headers={"X-Webhook-Secret": "wrong-secret"},
        json={"eventId": str(uuid4()), "userId": str(uuid4()), "planCode": "monthly"},
    )
    assert response.status_code == 401


def test_expired_pro_downgrades_safely_on_read(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "billing-expired@example.com")
    process_payment_event(
        db_session,
        external_event_id=str(uuid4()),
        user_id=user_id,
        plan_code="monthly",
    )
    db_session.commit()

    entitlements = EntitlementService(db_session)
    entitlement_row = db_session.get(UserEntitlement, user_id)
    assert entitlement_row is not None
    entitlement_row.active_until = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    status_row = entitlements.get_status(user_id)
    assert status_row.plan == SubscriptionPlan.FREE
    assert status_row.ai_daily_limit == 20

    db_session.commit()
    entitlement_row = db_session.get(UserEntitlement, user_id)
    assert entitlement_row is not None
    assert entitlement_row.plan == SubscriptionPlan.FREE
