"""Time-window resolution for market sessions (EP08-01).

Status is time-derived while a session is still scheduled/open: nobody has to run a
job to flip it, the same way fixture kickoff locks are derived from real time. Once a
session is explicitly closed or resolved by an admin action, that terminal state wins.
"""

from __future__ import annotations

from datetime import datetime

from database.enums import MarketSessionStatus
from market.models import MarketSession


def effective_status(session: MarketSession, *, now: datetime) -> MarketSessionStatus:
    """Resolve the session's status as of ``now``, without mutating it."""
    if session.status in (MarketSessionStatus.CLOSED, MarketSessionStatus.RESOLVED):
        return session.status
    if now < session.opens_at:
        return MarketSessionStatus.SCHEDULED
    if now < session.closes_at:
        return MarketSessionStatus.OPEN
    return MarketSessionStatus.CLOSED


def is_open_for_bids(session: MarketSession, *, now: datetime) -> bool:
    return effective_status(session, now=now) == MarketSessionStatus.OPEN
