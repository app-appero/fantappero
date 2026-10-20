"""Integration tests for push device registration (upsert by token, EP09-05)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from notifications.models import PushDevice
from notifications.service import NotificationService


def _register_and_login(client: TestClient, email: str) -> UUID:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    from mail.capture import get_captured_emails

    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return UUID(login.json()["user"]["id"])


def test_register_push_device_creates_row(client: TestClient, db_session: Session) -> None:
    user_id = _register_and_login(client, "push-create@example.com")
    service = NotificationService(db_session)

    response = service.register_push_device(
        user_id=user_id, token="ExponentPushToken[abc]", platform="ios"
    )
    db_session.commit()

    assert response.platform == "ios"
    row = db_session.scalar(select(PushDevice).where(PushDevice.token == "ExponentPushToken[abc]"))
    assert row is not None
    assert row.user_id == user_id
    assert row.revoked_at is None


def test_register_push_device_moves_token_to_new_owner(
    client: TestClient, db_session: Session
) -> None:
    first_user = _register_and_login(client, "push-first@example.com")
    second_user = _register_and_login(client, "push-second@example.com")
    service = NotificationService(db_session)

    service.register_push_device(
        user_id=first_user, token="ExponentPushToken[shared]", platform="ios"
    )
    db_session.commit()

    service.register_push_device(
        user_id=second_user, token="ExponentPushToken[shared]", platform="android"
    )
    db_session.commit()

    rows = db_session.scalars(
        select(PushDevice).where(PushDevice.token == "ExponentPushToken[shared]")
    ).all()
    assert len(rows) == 1
    assert rows[0].user_id == second_user
    assert rows[0].platform == "android"


def test_register_push_device_un_revokes_on_re_registration(
    client: TestClient, db_session: Session
) -> None:
    user_id = _register_and_login(client, "push-reregister@example.com")
    service = NotificationService(db_session)

    service.register_push_device(user_id=user_id, token="ExponentPushToken[stale]", platform="ios")
    db_session.commit()
    row = db_session.scalar(
        select(PushDevice).where(PushDevice.token == "ExponentPushToken[stale]")
    )
    assert row is not None
    from datetime import UTC, datetime

    row.revoked_at = datetime.now(UTC)
    db_session.commit()

    service.register_push_device(user_id=user_id, token="ExponentPushToken[stale]", platform="ios")
    db_session.commit()

    db_session.refresh(row)
    assert row.revoked_at is None


def test_unregister_push_device_removes_only_own_token(
    client: TestClient, db_session: Session
) -> None:
    owner = _register_and_login(client, "push-owner@example.com")
    other = _register_and_login(client, "push-other@example.com")
    service = NotificationService(db_session)

    service.register_push_device(user_id=owner, token="ExponentPushToken[mine]", platform="ios")
    db_session.commit()

    # un altro utente non puo' cancellare un token che non e' suo: no-op silenzioso.
    service.unregister_push_device(user_id=other, token="ExponentPushToken[mine]")
    db_session.commit()
    assert (
        db_session.scalar(select(PushDevice).where(PushDevice.token == "ExponentPushToken[mine]"))
        is not None
    )

    service.unregister_push_device(user_id=owner, token="ExponentPushToken[mine]")
    db_session.commit()
    assert (
        db_session.scalar(select(PushDevice).where(PushDevice.token == "ExponentPushToken[mine]"))
        is None
    )
