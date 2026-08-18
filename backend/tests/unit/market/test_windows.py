"""Unit tests for time-derived market session status (EP08-01)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from database.enums import MarketSessionStatus
from market.windows import effective_status, is_open_for_bids


@dataclass
class _FakeSession:
    """Duck-typed stand-in for ``MarketSession`` (avoids configuring the full ORM registry)."""

    status: MarketSessionStatus
    opens_at: datetime
    closes_at: datetime


def _session(
    *, status: MarketSessionStatus, opens_delta: timedelta, closes_delta: timedelta
) -> _FakeSession:
    now = datetime.now(UTC)
    return _FakeSession(
        status=status,
        opens_at=now + opens_delta,
        closes_at=now + closes_delta,
    )


def test_effective_status_is_scheduled_before_window() -> None:
    session = _session(
        status=MarketSessionStatus.SCHEDULED,
        opens_delta=timedelta(hours=1),
        closes_delta=timedelta(hours=2),
    )
    assert effective_status(session, now=datetime.now(UTC)) == MarketSessionStatus.SCHEDULED
    assert not is_open_for_bids(session, now=datetime.now(UTC))


def test_effective_status_is_open_within_window() -> None:
    session = _session(
        status=MarketSessionStatus.SCHEDULED,
        opens_delta=timedelta(hours=-1),
        closes_delta=timedelta(hours=1),
    )
    assert effective_status(session, now=datetime.now(UTC)) == MarketSessionStatus.OPEN
    assert is_open_for_bids(session, now=datetime.now(UTC))


def test_effective_status_is_closed_after_deadline() -> None:
    session = _session(
        status=MarketSessionStatus.SCHEDULED,
        opens_delta=timedelta(hours=-2),
        closes_delta=timedelta(hours=-1),
    )
    assert effective_status(session, now=datetime.now(UTC)) == MarketSessionStatus.CLOSED
    assert not is_open_for_bids(session, now=datetime.now(UTC))


def test_effective_status_terminal_states_are_sticky() -> None:
    session = _session(
        status=MarketSessionStatus.RESOLVED,
        opens_delta=timedelta(hours=-2),
        closes_delta=timedelta(hours=1),
    )
    # Even though "now" falls inside the raw window, resolution is terminal.
    assert effective_status(session, now=datetime.now(UTC)) == MarketSessionStatus.RESOLVED

    closed_session = _session(
        status=MarketSessionStatus.CLOSED,
        opens_delta=timedelta(hours=-2),
        closes_delta=timedelta(hours=1),
    )
    assert effective_status(closed_session, now=datetime.now(UTC)) == MarketSessionStatus.CLOSED
