"""Email delivery for in-app notifications: gating (EP09-05, Task 6b).

Nessuna chiamata di rete reale: sessioni/profili finti (``SimpleNamespace``),
stesso approccio di ``test_push.py``. Il task 6b spegne di default l'email
per le notifiche di gioco "di routine" (sistema/formazione/mercato/
risultati) mantenendo intatti i canali in-app e push: qui verifichiamo
l'interruttore globale ``NOTIFICATIONS_ROUTINE_EMAIL_ENABLED`` oltre al
toggle di profilo e alle quiete già esistenti.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from notifications.email_dispatch import dispatch_notification_email


def _notification(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "category": SimpleNamespace(value="mercato"),
        "title": "Titolo",
        "body": "Corpo",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _profile(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "notifications_email": True,
        "timezone": "Europe/Rome",
        "quiet_hours_start_hour": None,
        "quiet_hours_end_hour": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), email="test@example.com")


def test_dispatch_email_skips_without_profile() -> None:
    # Nessuna eccezione, nessun task: come in test_push.py non possiamo
    # verificare il mock del task senza patchare l'import deferred, quindi
    # verifichiamo solo che non esploda e ritorni silenziosamente.
    dispatch_notification_email(notification=_notification(), user=_user(), profile=None)


def test_dispatch_email_skips_when_profile_toggle_off() -> None:
    dispatch_notification_email(
        notification=_notification(),
        user=_user(),
        profile=_profile(notifications_email=False),
    )


def test_dispatch_email_skips_by_default_routine_kill_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 6b: di default le email di notifica "di routine" sono spente."""
    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    monkeypatch.setattr("mail.tasks.send_message_task", _FakeTask())
    fake_settings = SimpleNamespace(notifications_routine_email_enabled=False)
    monkeypatch.setattr(
        "notifications.email_dispatch.get_api_settings", lambda: fake_settings
    )

    dispatch_notification_email(
        notification=_notification(), user=_user(), profile=_profile()
    )
    assert sent == []


def test_dispatch_email_enqueues_when_kill_switch_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    monkeypatch.setattr("mail.tasks.send_message_task", _FakeTask())
    fake_settings = SimpleNamespace(notifications_routine_email_enabled=True)
    monkeypatch.setattr(
        "notifications.email_dispatch.get_api_settings", lambda: fake_settings
    )
    user = _user()
    notification = _notification()

    dispatch_notification_email(notification=notification, user=user, profile=_profile())

    assert len(sent) == 1
    assert sent[0]["to_email"] == user.email
    assert sent[0]["subject"] == notification.title
    assert sent[0]["template"] == "notification.mercato"


def test_dispatch_email_respects_quiet_hours_when_kill_switch_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    monkeypatch.setattr("mail.tasks.send_message_task", _FakeTask())
    fake_settings = SimpleNamespace(notifications_routine_email_enabled=True)
    monkeypatch.setattr(
        "notifications.email_dispatch.get_api_settings", lambda: fake_settings
    )
    monkeypatch.setattr(
        "notifications.email_dispatch.is_within_quiet_hours", lambda **kwargs: True
    )

    dispatch_notification_email(
        notification=_notification(), user=_user(), profile=_profile()
    )
    assert sent == []
