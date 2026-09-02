"""Integration tests for NotificationService: dedup, preferences, mark-all-read (EP09-01)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.enums import NotificationCategory
from mail.capture import get_captured_emails
from notifications.service import NotificationService


def _register_and_login(client: TestClient, email: str) -> UUID:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return UUID(login.json()["user"]["id"])


def test_create_notification_is_deduplicated(client: TestClient, db_session: Session) -> None:
    user_id = _register_and_login(client, "notif-dedup@example.com")
    service = NotificationService(db_session)

    first, created_first = service.create_notification(
        user_id=user_id,
        category=NotificationCategory.SISTEMA,
        template_key="sistema.generico",
        template_version=1,
        params={"title": "Ciao", "body": "Prova"},
        dedup_key="test:dedup:1",
    )
    second, created_second = service.create_notification(
        user_id=user_id,
        category=NotificationCategory.SISTEMA,
        template_key="sistema.generico",
        template_version=1,
        params={"title": "Ciao", "body": "Prova"},
        dedup_key="test:dedup:1",
    )
    db_session.commit()

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert created_first is True
    assert created_second is False
    assert service.list_notifications(user_id=user_id).total == 1


def test_create_notification_skips_when_preference_disabled(
    client: TestClient, db_session: Session
) -> None:
    user_id = _register_and_login(client, "notif-pref@example.com")
    service = NotificationService(db_session)

    service.update_preference(
        user_id=user_id, category=NotificationCategory.MERCATO, in_app_enabled=False
    )
    db_session.commit()

    created, was_created = service.create_notification(
        user_id=user_id,
        category=NotificationCategory.MERCATO,
        template_key="sistema.generico",
        template_version=1,
        params={"title": "Mercato", "body": "Evento"},
        dedup_key="test:pref:1",
    )
    db_session.commit()

    assert created is None
    assert was_created is False
    listing = service.list_notifications(user_id=user_id, category=NotificationCategory.MERCATO)
    assert listing.total == 0


def test_mark_all_read_marks_only_own_unread(client: TestClient, db_session: Session) -> None:
    user_id = _register_and_login(client, "notif-readall@example.com")
    other_user_id = _register_and_login(client, "notif-readall-other@example.com")
    service = NotificationService(db_session)

    for i in range(3):
        service.create_notification(
            user_id=user_id,
            category=NotificationCategory.SISTEMA,
            template_key="sistema.generico",
            template_version=1,
            params={"title": f"T{i}", "body": "B"},
            dedup_key=f"test:readall:{i}",
        )
    service.create_notification(
        user_id=other_user_id,
        category=NotificationCategory.SISTEMA,
        template_key="sistema.generico",
        template_version=1,
        params={"title": "Altro", "body": "B"},
        dedup_key="test:readall:other",
    )
    db_session.commit()

    result = service.mark_all_read(user_id=user_id)
    db_session.commit()

    assert result.marked_count == 3
    assert service.list_notifications(user_id=user_id, unread_only=True).total == 0
    assert service.list_notifications(user_id=other_user_id, unread_only=True).total == 1
