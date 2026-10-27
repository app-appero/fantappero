"""Integration tests for external-channel (email) notification delivery (EP09-05).

Task 6b spegne di default l'email per le notifiche "di routine" (sistema/
formazione/mercato/risultati): resta solo in-app/push finché l'operatore
non riattiva ``NOTIFICATIONS_ROUTINE_EMAIL_ENABLED`` (vedi
docs/operations/email_notifications.md). I test che riguardano il
comportamento *con* l'interruttore acceso (opt-in, quiete, dedup) attivano
esplicitamente il flag.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from config.settings.loader import reset_settings_cache
from database.enums import NotificationCategory
from mail.capture import get_captured_emails
from notifications.service import NotificationService


def _enable_routine_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATIONS_ROUTINE_EMAIL_ENABLED", "true")
    reset_settings_cache()


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


def _create_notification(db_session: Session, user_id: UUID, dedup_key: str) -> None:
    NotificationService(db_session).create_notification(
        user_id=user_id,
        category=NotificationCategory.SISTEMA,
        template_key="sistema.generico",
        template_version=1,
        params={"title": "Ciao", "body": "Hai un aggiornamento"},
        dedup_key=dedup_key,
    )
    db_session.commit()


def test_email_not_sent_by_default_even_when_opted_in(
    client: TestClient, db_session: Session
) -> None:
    """Task 6b: il kill switch globale è spento di default — niente email."""
    token, user_id = _register_and_login(client, "email-default-off@example.com")
    before = len(get_captured_emails())

    _create_notification(db_session, user_id, "test:email:default-off")

    assert len(get_captured_emails()) == before


def test_email_sent_when_opted_in_and_routine_switch_enabled(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_routine_email(monkeypatch)
    token, user_id = _register_and_login(client, "email-optin@example.com")
    before = len(get_captured_emails())

    _create_notification(db_session, user_id, "test:email:optin")

    after = get_captured_emails()
    assert len(after) == before + 1
    assert after[-1].to_email == "email-optin@example.com"
    assert after[-1].message.subject == "Ciao"


def test_email_not_sent_after_opting_out(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_routine_email(monkeypatch)
    token, user_id = _register_and_login(client, "email-optout@example.com")
    patch = client.patch(
        "/profile/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"notificationsEmail": False},
    )
    assert patch.status_code == 200
    before = len(get_captured_emails())

    _create_notification(db_session, user_id, "test:email:optout")

    assert len(get_captured_emails()) == before


def test_email_suppressed_during_configured_quiet_hours(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_routine_email(monkeypatch)
    token, user_id = _register_and_login(client, "email-quiet@example.com")
    local_hour = datetime.now(UTC).astimezone(ZoneInfo("Europe/Rome")).hour
    patch = client.patch(
        "/profile/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "timezone": "Europe/Rome",
            "quietHoursStartHour": local_hour,
            "quietHoursEndHour": (local_hour + 1) % 24,
        },
    )
    assert patch.status_code == 200
    before = len(get_captured_emails())

    _create_notification(db_session, user_id, "test:email:quiet")

    assert len(get_captured_emails()) == before


def test_email_not_resent_on_dedup_replay(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_routine_email(monkeypatch)
    token, user_id = _register_and_login(client, "email-dedup@example.com")

    _create_notification(db_session, user_id, "test:email:dedup")
    after_first = len(get_captured_emails())
    _create_notification(db_session, user_id, "test:email:dedup")

    assert len(get_captured_emails()) == after_first
