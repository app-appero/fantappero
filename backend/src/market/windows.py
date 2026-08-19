"""Time-window resolution for market sessions (EP08-01).

Status is time-derived while a session is still scheduled/open: nobody has to run a
job to flip it, the same way fixture kickoff locks are derived from real time. Once a
session is explicitly closed or resolved by an admin action, that terminal state wins.
"""

from __future__ import annotations

from datetime import datetime

from database.enums import MarketSessionStatus, TradeStatus
from market.models import MarketSession, TradeProposal


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


def effective_trade_status(proposal: TradeProposal, *, now: datetime) -> TradeStatus:
    """Resolve a trade proposal's status as of ``now`` (Doc §17 'Scambio').

    A ``PROPOSED`` trade past its deadline reads as ``EXPIRED`` even before anyone
    (EP08-06) has persisted the transition — "offerte scadute non sono accettabili".
    Any other status is already terminal (or will be handled by EP08-06/07's own
    transitions) and wins as-is.
    """
    if proposal.status != TradeStatus.PROPOSED:
        return proposal.status
    if now >= proposal.expires_at:
        return TradeStatus.EXPIRED
    return TradeStatus.PROPOSED


def is_trade_actionable(proposal: TradeProposal, *, now: datetime) -> bool:
    """Whether the proposal is still pending and not yet expired/withdrawn."""
    return effective_trade_status(proposal, now=now) == TradeStatus.PROPOSED
