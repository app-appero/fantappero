"""Eventi in tempo reale: classificazione dei percorsi, pubblicazione a commit, middleware."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from realtime import middleware, publisher
from realtime.middleware import RealtimeMarketMiddleware, market_event

LEAGUE = str(uuid4())
SESSION = str(uuid4())


def test_market_paths_are_classified() -> None:
    channel, payload = market_event(f"/leagues/{LEAGUE}/mercato/scambi/proposte")  # type: ignore[misc]
    assert channel == f"rt:league:{LEAGUE}"
    assert payload == {"type": "market.updated", "kind": "trades", "leagueId": LEAGUE}
    _, live = market_event(  # type: ignore[misc]
        f"/leagues/{LEAGUE}/mercato/asta-live/sessioni/{SESSION}/lotti/nomina"
    )
    assert live["kind"] == "auction_live"
    assert live["sessionId"] == SESSION
    _, other = market_event(f"/leagues/{LEAGUE}/mercato/buste")  # type: ignore[misc]
    assert other["kind"] == "market"


def test_other_paths_are_ignored() -> None:
    assert market_event(f"/leagues/{LEAGUE}/rosa") is None
    assert market_event("/notifications") is None
    assert market_event("/leagues/not-a-uuid/mercato/scambi") is None


def _run(method: str, path: str, status: int, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    published: list[tuple] = []
    monkeypatch.setattr(middleware, "publish", lambda *a: published.append(a))

    async def app(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(_message) -> None:
        return None

    asyncio.run(
        RealtimeMarketMiddleware(app)(
            {"type": "http", "method": method, "path": path}, None, send
        )
    )
    return published


def test_middleware_publishes_after_successful_market_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published = _run("POST", f"/leagues/{LEAGUE}/mercato/scambi/proposte", 201, monkeypatch)
    assert len(published) == 1
    assert published[0][1]["kind"] == "trades"


def test_middleware_ignores_reads_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run("GET", f"/leagues/{LEAGUE}/mercato/scambi/proposte", 200, monkeypatch) == []
    assert _run("POST", f"/leagues/{LEAGUE}/mercato/scambi/proposte", 422, monkeypatch) == []


def test_publish_after_commit_waits_for_commit_and_drops_on_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple] = []
    monkeypatch.setattr(publisher, "publish", lambda channel, payload: sent.append(channel))
    engine = create_engine("sqlite://")
    with Session(engine) as session:
        session.execute(text("select 1"))
        publisher.publish_after_commit(session, "rt:user:a", {"type": "x"})
        assert sent == []
        session.commit()
        assert sent == ["rt:user:a"]
        session.execute(text("select 1"))
        publisher.publish_after_commit(session, "rt:user:b", {"type": "x"})
        session.rollback()
        session.commit()
        assert sent == ["rt:user:a"]


def test_publish_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    broken = MagicMock()
    broken.publish.side_effect = RuntimeError("redis giu")
    monkeypatch.setattr(publisher, "_client", lambda: broken)
    publisher.publish("rt:user:a", {"type": "x"})
    monkeypatch.setattr(publisher, "_client", lambda: None)
    publisher.publish("rt:user:a", {"type": "x"})
