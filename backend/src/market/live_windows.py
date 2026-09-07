"""Time-window resolution for live-auction lots (EP08-09).

Same philosophy as ``market/windows.py``: a lot's window is time-derived while
it is still open — nobody has to run a background job to flip it. The actual
finalization (auto-sell to the leader, or auto-pass) happens lazily in
``LiveMarketService._tick_current_lot`` the next time any request touches the
session (a poll, a raise, an operator action), not here.
"""

from __future__ import annotations

from datetime import datetime

from database.enums import MarketLiveLotStatus
from market.live_models import MarketLiveLot


def lot_window_is_open(lot: MarketLiveLot, *, now: datetime) -> bool:
    """Whether the lot is still accepting raises as of ``now``."""
    return lot.status == MarketLiveLotStatus.OPEN and now < lot.closes_at


def lot_is_expired(lot: MarketLiveLot, *, now: datetime) -> bool:
    """Whether the lot's window has passed but it has not been finalized yet."""
    return lot.status == MarketLiveLotStatus.OPEN and now >= lot.closes_at
