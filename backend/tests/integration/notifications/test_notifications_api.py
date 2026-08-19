"""Integration tests for the /notifications HTTP API (EP09-01)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.enums import NotificationCategory
from mail.capture import get_captured_emails
from notifications.service import NotificationService


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


def test_list_notifications_empty_state(client: TestClient) -> None:
    token, _ = _register_and_login(client, "notif-api-empty@example.com")
    response = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["unreadCount"] == 0


def test_list_notifications_without_token_is_unauthorized(client: TestClient) -> None:
    response = client.get("/notifications")
    assert response.status_code == 401


def test_list_and_mark_read_positive_flow(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "notif-api-flow@example.com")
    service = NotificationService(db_session)
    notification, _ = service.create_notification(
        user_id=user_id,
        category=NotificationCategory.SISTEMA,
        template_key="sistema.generico",
        template_version=1,
        params={"title": "Benvenuto", "body": "Ciao", "deep_link": "/app/home"},
        dedup_key="test:api:flow:1",
    )
    db_session.commit()
    assert notification is not None

    listing = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["unreadCount"] == 1
    item = body["items"][0]
    assert item["title"] == "Benvenuto"
    assert item["deepLink"] == "/app/home"
    assert item["read"] is False

    mark = client.post(
        f"/notifications/{item['id']}/read", headers={"Authorization": f"Bearer {token}"}
    )
    assert mark.status_code == 200
    assert mark.json()["read"] is True

    listing_after = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
    assert listing_after.json()["unreadCount"] == 0


def test_mark_read_on_other_users_notification_is_not_found(
    client: TestClient, db_session: Session
) -> None:
    _, owner_id = _register_and_login(client, "notif-api-owner@example.com")
    intruder_token, _ = _register_and_login(client, "notif-api-intruder@example.com")
    service = NotificationService(db_session)
    notification, _ = service.create_notification(
        user_id=owner_id,
        category=NotificationCategory.SISTEMA,
        template_key="sistema.generico",
        template_version=1,
        params={"title": "Privato", "body": "Solo owner"},
        dedup_key="test:api:idor:1",
    )
    db_session.commit()
    assert notification is not None

    response = client.post(
        f"/notifications/{notification.id}/read",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert response.status_code == 404


def test_mark_all_read_endpoint(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "notif-api-readall@example.com")
    service = NotificationService(db_session)
    for i in range(2):
        service.create_notification(
            user_id=user_id,
            category=NotificationCategory.SISTEMA,
            template_key="sistema.generico",
            template_version=1,
            params={"title": f"T{i}", "body": "B"},
            dedup_key=f"test:api:readall:{i}",
        )
    db_session.commit()

    response = client.post("/notifications/read-all", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["markedCount"] == 2


def test_preferences_default_enabled_and_can_be_updated(client: TestClient) -> None:
    token, _ = _register_and_login(client, "notif-api-prefs@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    defaults = client.get("/notifications/preferences", headers=headers)
    assert defaults.status_code == 200
    assert all(item["inAppEnabled"] is True for item in defaults.json()["items"])

    updated = client.put(
        "/notifications/preferences",
        headers=headers,
        json={"category": "mercato", "inAppEnabled": False},
    )
    assert updated.status_code == 200
    items_by_category = {item["category"]: item["inAppEnabled"] for item in updated.json()["items"]}
    assert items_by_category["mercato"] is False
    assert items_by_category["sistema"] is True
