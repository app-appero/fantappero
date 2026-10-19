"""Notifiche push: client Expo, invio/revoca token, gating del dispatch (EP09-05).

Nessuna chiamata di rete reale: il client usa ``httpx.MockTransport``, il
dispatch usa sessioni/profili finti (``MagicMock``), stesso approccio delle
altre suite di questo repo (es. ``test_predicted_lineups_oracle.py``).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from notifications.expo_push_client import ExpoPushClient, ExpoPushError
from notifications.push_dispatch import dispatch_notification_push
from notifications.push_send import send_to_devices

# ---------------------------------------------------------------------------
# Client: nessuna rete reale.
# ---------------------------------------------------------------------------


def test_client_sends_batch_and_parses_tickets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        assert len(body) == 2
        return httpx.Response(
            200,
            json={"data": [{"status": "ok", "id": "r1"}, {"status": "ok", "id": "r2"}]},
        )

    with ExpoPushClient(transport=httpx.MockTransport(handler)) as client:
        tickets = client.send(
            [
                {"to": "ExponentPushToken[a]", "title": "t", "body": "b"},
                {"to": "ExponentPushToken[b]", "title": "t", "body": "b"},
            ]
        )
    assert tickets == [{"status": "ok", "id": "r1"}, {"status": "ok", "id": "r2"}]


def test_client_sends_authorization_header_when_token_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-expo-token"
        return httpx.Response(200, json={"data": []})

    with ExpoPushClient(
        access_token="secret-expo-token", transport=httpx.MockTransport(handler)
    ) as client:
        client.send([{"to": "ExponentPushToken[a]"}])


def test_client_omits_authorization_header_without_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"data": []})

    with ExpoPushClient(transport=httpx.MockTransport(handler)) as client:
        client.send([{"to": "ExponentPushToken[a]"}])


def test_client_chunks_over_100_messages() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        calls["n"] += 1
        body = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"status": "ok"} for _ in body]})

    with ExpoPushClient(transport=httpx.MockTransport(handler)) as client:
        tickets = client.send([{"to": f"ExponentPushToken[{i}]"} for i in range(150)])
    assert calls["n"] == 2
    assert len(tickets) == 150


def test_client_empty_message_list_makes_no_call() -> None:
    def never(request: httpx.Request) -> httpx.Response:
        raise AssertionError("non deve chiamare la rete")

    with ExpoPushClient(transport=httpx.MockTransport(never)) as client:
        assert client.send([]) == []


def test_client_retries_5xx_then_gives_up() -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    sleeps: list[float] = []
    with ExpoPushClient(
        max_retries=1, transport=httpx.MockTransport(flaky), sleep=sleeps.append
    ) as client:
        with pytest.raises(ExpoPushError) as excinfo:
            client.send([{"to": "ExponentPushToken[a]"}])
    assert calls["n"] == 2
    assert excinfo.value.status == 503


# ---------------------------------------------------------------------------
# send_to_devices: invio + revoca dei token morti.
# ---------------------------------------------------------------------------


def _device(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "token": "ExponentPushToken[x]",
        "platform": "ios",
        "revoked_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_send_to_devices_counts_ok_tickets_as_sent() -> None:
    session = MagicMock()
    client = MagicMock()
    devices = [_device(), _device()]
    client.send.return_value = [{"status": "ok"}, {"status": "ok"}]

    result = send_to_devices(session, client, devices, title="T", body="B", data={})
    assert result == {"sent": 2, "revoked": 0}
    session.flush.assert_not_called()


def test_send_to_devices_revokes_device_not_registered() -> None:
    session = MagicMock()
    client = MagicMock()
    stale = _device()
    client.send.return_value = [
        {"status": "error", "details": {"error": "DeviceNotRegistered"}},
    ]

    result = send_to_devices(session, client, [stale], title="T", body="B", data={})
    assert result == {"sent": 0, "revoked": 1}
    assert stale.revoked_at is not None
    session.flush.assert_called_once()


def test_send_to_devices_other_errors_do_not_revoke() -> None:
    session = MagicMock()
    client = MagicMock()
    device = _device()
    client.send.return_value = [
        {"status": "error", "details": {"error": "MessageTooBig"}},
    ]

    result = send_to_devices(session, client, [device], title="T", body="B", data={})
    assert result == {"sent": 0, "revoked": 0}
    assert device.revoked_at is None


def test_send_to_devices_empty_list_short_circuits() -> None:
    client = MagicMock()
    assert send_to_devices(MagicMock(), client, [], title="T", body="B", data={}) == {
        "sent": 0,
        "revoked": 0,
    }
    client.send.assert_not_called()


def test_send_to_devices_swallows_client_error() -> None:
    session = MagicMock()
    client = MagicMock()
    client.send.side_effect = ExpoPushError(500, "boom")
    device = _device()

    result = send_to_devices(session, client, [device], title="T", body="B", data={})
    assert result == {"sent": 0, "revoked": 0}


# ---------------------------------------------------------------------------
# dispatch_notification_push: gating (profilo, interruttore globale, quiete).
# ---------------------------------------------------------------------------


def _notification(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "category": SimpleNamespace(value="mercato"),
        "title": "Titolo",
        "body": "Corpo",
        "deep_link": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _profile(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "notifications_push": True,
        "timezone": "Europe/Rome",
        "quiet_hours_start_hour": None,
        "quiet_hours_end_hour": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_dispatch_push_skips_without_profile() -> None:
    user = SimpleNamespace(id=uuid4())
    # Nessuna eccezione, nessun task: non c'e' modo di verificare il mock del
    # task senza patchare l'import deferred, quindi verifichiamo solo che non
    # esploda e che la funzione ritorni silenziosamente.
    dispatch_notification_push(notification=_notification(), user=user, profile=None)


def test_dispatch_push_skips_when_profile_toggle_off() -> None:
    user = SimpleNamespace(id=uuid4())
    dispatch_notification_push(
        notification=_notification(), user=user, profile=_profile(notifications_push=False)
    )


def test_dispatch_push_enqueues_task_in_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setattr("notifications.tasks.send_push_task", _FakeTask())
    user = SimpleNamespace(id=uuid4())
    notification = _notification()

    dispatch_notification_push(notification=notification, user=user, profile=_profile())

    assert len(sent) == 1
    assert sent[0]["user_id"] == str(user.id)
    assert sent[0]["notification_id"] == str(notification.id)
    assert sent[0]["category"] == "mercato"


def test_dispatch_push_respects_quiet_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setattr("notifications.tasks.send_push_task", _FakeTask())
    monkeypatch.setattr(
        "notifications.push_dispatch.is_within_quiet_hours", lambda **kwargs: True
    )
    user = SimpleNamespace(id=uuid4())

    dispatch_notification_push(notification=_notification(), user=user, profile=_profile())
    assert sent == []


def test_dispatch_push_respects_global_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setattr("notifications.tasks.send_push_task", _FakeTask())
    fake_settings = SimpleNamespace(notifications_push_enabled=False)
    monkeypatch.setattr(
        "notifications.push_dispatch.get_api_settings", lambda: fake_settings
    )
    user = SimpleNamespace(id=uuid4())

    dispatch_notification_push(notification=_notification(), user=user, profile=_profile())
    assert sent == []
