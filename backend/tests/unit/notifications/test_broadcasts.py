"""Avvisi dell'operatore: validazioni, invio, programmati, prove (EP09-06)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from notifications import broadcast_service as svc
from notifications.admin_router import CreateBroadcastRequest, list_samples
from notifications.broadcast_service import BroadcastError

ALL = {"mode": "all", "leagueIds": [], "userIds": [], "excludeUserIds": []}


def _create(session: MagicMock, **overrides: object):
    args: dict[str, object] = {
        "created_by": uuid4(),
        "kind": "avviso",
        "title": "Titolo",
        "body": "Testo",
        "category": "sistema",
        "deep_link": None,
        "channels": {"inApp": True, "push": False, "email": False},
        "audience": ALL,
        "scheduled_at": None,
    }
    args.update(overrides)
    return svc.create_broadcast(session, **args)  # type: ignore[arg-type]


def _patch_audience(monkeypatch: pytest.MonkeyPatch, users: list) -> list[object]:
    monkeypatch.setattr(svc, "resolve_audience", lambda s, a: users)
    monkeypatch.setattr(svc, "audience_label", lambda *a: "Tutti gli utenti")
    delivered: list[object] = []
    monkeypatch.setattr(svc, "deliver", lambda s, b: delivered.append(b))
    return delivered


@pytest.mark.parametrize("link", ["/turni", "/formazione?x=1", "/scambi/123", "/inviti"])
def test_valid_deep_links(link: str) -> None:
    svc.validate_deep_link(link)


@pytest.mark.parametrize("link", ["https://x.it", "//evil.it", "turni", "/admin", "/lega"])
def test_invalid_deep_links(link: str) -> None:
    with pytest.raises(BroadcastError) as exc:
        svc.validate_deep_link(link)
    assert exc.value.code == "invalid_deep_link"


def test_email_channel_is_rejected_for_now() -> None:
    with pytest.raises(BroadcastError) as exc:
        _create(MagicMock(), channels={"inApp": True, "push": False, "email": True})
    assert exc.value.code == "email_unavailable"


def test_unknown_kind_and_category_are_rejected() -> None:
    with pytest.raises(BroadcastError):
        _create(MagicMock(), kind="spam")
    with pytest.raises(BroadcastError):
        _create(MagicMock(), category="altro")


def test_empty_audience_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_audience(monkeypatch, [])
    with pytest.raises(BroadcastError) as exc:
        _create(MagicMock())
    assert exc.value.code == "empty_audience"


def test_immediate_broadcast_delivers(monkeypatch: pytest.MonkeyPatch) -> None:
    delivered = _patch_audience(monkeypatch, [uuid4(), uuid4()])
    broadcast = _create(MagicMock())
    assert delivered == [broadcast]
    assert broadcast.scheduled_at is None
    assert broadcast.channels == {"inApp": True, "push": False, "email": False}


def test_future_broadcast_is_only_scheduled(monkeypatch: pytest.MonkeyPatch) -> None:
    delivered = _patch_audience(monkeypatch, [uuid4()])
    when = datetime.now(UTC) + timedelta(hours=2)
    broadcast = _create(MagicMock(), scheduled_at=when)
    assert delivered == []
    assert broadcast.status == "scheduled"
    assert broadcast.scheduled_at == when


def test_past_schedule_sends_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    delivered = _patch_audience(monkeypatch, [uuid4()])
    _create(MagicMock(), scheduled_at=datetime.now(UTC) - timedelta(minutes=5))
    assert len(delivered) == 1


class _RecordingService:
    calls: list[dict[str, object]] = []

    def __init__(self, session: object) -> None:
        pass

    def create_notification(self, **kwargs: object) -> tuple[None, bool]:
        _RecordingService.calls.append(kwargs)
        return None, True


def _broadcast(push: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        audience=ALL,
        channels={"push": push},
        category="sistema",
        title="T",
        body="B",
        deep_link="/turni",
    )


def test_deliver_creates_one_notification_per_user_with_dedup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users = [uuid4(), uuid4()]
    monkeypatch.setattr(svc, "resolve_audience", lambda s, a: users)
    monkeypatch.setattr(svc, "NotificationService", _RecordingService)
    _RecordingService.calls = []
    session = MagicMock()
    session.scalar.return_value = 1
    broadcast = _broadcast(push=True)
    svc.deliver(session, broadcast)  # type: ignore[arg-type]
    calls = _RecordingService.calls
    assert [c["user_id"] for c in calls] == users
    assert all(c["dedup_key"] == f"broadcast:{broadcast.id}:{c['user_id']}" for c in calls)
    assert all(c["push"] is True and c["email"] is False for c in calls)
    assert broadcast.status == "sent"
    assert broadcast.recipient_count == 2
    assert broadcast.push_count == 1


def test_deliver_without_push_never_pushes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "resolve_audience", lambda s, a: [uuid4()])
    monkeypatch.setattr(svc, "NotificationService", _RecordingService)
    _RecordingService.calls = []
    broadcast = _broadcast(push=False)
    svc.deliver(MagicMock(), broadcast)  # type: ignore[arg-type]
    assert _RecordingService.calls[0]["push"] is False
    assert broadcast.push_count == 0


def test_dispatch_due_sends_and_restores_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ok = SimpleNamespace(status="scheduled")
    bad = SimpleNamespace(status="scheduled")
    session = MagicMock()
    session.scalars.return_value.all.return_value = [ok, bad]

    def fake_deliver(s: object, b: SimpleNamespace) -> None:
        if b is bad:
            raise RuntimeError("boom")
        b.status = "sent"

    monkeypatch.setattr(svc, "deliver", fake_deliver)
    assert svc.dispatch_due(session, now=datetime.now(UTC)) == 2
    assert ok.status == "sent"
    assert bad.status == "scheduled"


def test_cancel_only_scheduled() -> None:
    session = MagicMock()
    row = SimpleNamespace(status="scheduled")
    session.get.return_value = row
    assert svc.cancel_scheduled(session, uuid4()) is True
    assert row.status == "cancelled"
    row.status = "sent"
    assert svc.cancel_scheduled(session, uuid4()) is False
    session.get.return_value = None
    assert svc.cancel_scheduled(session, uuid4()) is False


def test_request_contract_uses_camel_case_names() -> None:
    body = CreateBroadcastRequest.model_validate(
        {
            "kind": "novita",
            "title": "T",
            "body": "B",
            "category": "sistema",
            "deepLink": "/turni",
            "channels": {"inApp": True, "push": True, "email": False},
            "audience": {"mode": "leagues", "leagueIds": [str(uuid4())], "excludeUserIds": []},
            "scheduledAt": "2026-11-01T10:00:00Z",
        }
    )
    assert body.channels.push is True
    assert body.audience.mode == "leagues"
    assert body.scheduled_at is not None


def test_sample_list_renders_every_sample() -> None:
    items = list_samples(_operator=SimpleNamespace()).items  # type: ignore[arg-type]
    assert items
    assert all(i.title and i.body and i.category for i in items)
