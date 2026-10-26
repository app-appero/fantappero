"""Integration tests for NotificationService: dedup, preferences, mark-all-read (EP09-01)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
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


def test_create_notification_skips_when_event_preference_disabled(
    client: TestClient, db_session: Session
) -> None:
    """TASK5: spegnere il singolo evento "gol" non deve zittire tutta la
    categoria "risultati" (es. l'omologazione del turno deve continuare ad
    arrivare)."""
    user_id = _register_and_login(client, "notif-event-pref@example.com")
    service = NotificationService(db_session)

    service.update_event_preference(
        user_id=user_id, event_key="calciatori.gol", in_app_enabled=False, push_enabled=None
    )
    db_session.commit()

    goal, goal_created = service.create_notification(
        user_id=user_id,
        category=NotificationCategory.RISULTATI,
        template_key="risultati.gol",
        template_version=2,
        params={"player": "Bomber", "minute": 10},
        dedup_key="test:event-pref:goal",
    )
    omologazione, omologazione_created = service.create_notification(
        user_id=user_id,
        category=NotificationCategory.RISULTATI,
        template_key="risultati.omologazione",
        template_version=1,
        params={"round_number": 7},
        dedup_key="test:event-pref:omologazione",
    )
    db_session.commit()

    assert goal is None
    assert goal_created is False
    assert omologazione is not None
    assert omologazione_created is True
    assert service.list_notifications(user_id=user_id).total == 1


def test_create_notification_with_push_disabled_still_creates_in_app_row(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TASK5: push e in-app sono canali indipendenti. Spegnere solo la push
    su un evento deve lasciare intatta la notifica in-app (la campanella),
    sopprimendo solo l'invio push per quella notifica."""
    import notifications.service as service_module

    dispatched: list[str] = []
    monkeypatch.setattr(
        service_module,
        "dispatch_notification_push",
        lambda **kwargs: dispatched.append(kwargs["notification"].dedup_key),
    )

    user_id = _register_and_login(client, "notif-push-pref@example.com")
    service = NotificationService(db_session)
    service.update_event_preference(
        user_id=user_id, event_key="calciatori.gol", in_app_enabled=None, push_enabled=False
    )
    db_session.commit()

    notification, created = service.create_notification(
        user_id=user_id,
        category=NotificationCategory.RISULTATI,
        template_key="risultati.gol",
        template_version=2,
        params={"player": "Bomber", "minute": 10},
        dedup_key="test:push-pref:goal",
    )
    db_session.commit()

    assert notification is not None
    assert created is True
    assert service.list_notifications(user_id=user_id).total == 1
    assert dispatched == []


def test_get_preferences_includes_granular_events_defaulting_to_enabled(
    client: TestClient, db_session: Session
) -> None:
    user_id = _register_and_login(client, "notif-event-defaults@example.com")
    service = NotificationService(db_session)

    preferences = service.get_preferences(user_id=user_id)
    events_by_key = {event.event_key: event for event in preferences.events}
    assert "calciatori.gol" in events_by_key
    assert "sistema.asta" in events_by_key
    assert events_by_key["calciatori.gol"].in_app_enabled is True
    assert events_by_key["calciatori.gol"].push_enabled is True

    service.update_event_preference(
        user_id=user_id, event_key="calciatori.gol", in_app_enabled=False, push_enabled=None
    )
    db_session.commit()

    refreshed = service.get_preferences(user_id=user_id)
    refreshed_by_key = {event.event_key: event for event in refreshed.events}
    assert refreshed_by_key["calciatori.gol"].in_app_enabled is False
    # push_enabled non è stato toccato (None nell'update): resta sul default.
    assert refreshed_by_key["calciatori.gol"].push_enabled is True
    # Gli altri eventi non sono stati sfiorati.
    assert refreshed_by_key["calciatori.assist"].in_app_enabled is True


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
