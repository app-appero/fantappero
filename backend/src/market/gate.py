"""League-admin market window: rosa and auctions vs always-on trades."""

from __future__ import annotations

from typing import Protocol

from auth.exceptions import ValidationAuthError

MARKET_CLOSED_CODE = "market_closed"
MARKET_CLOSED_MESSAGE = (
    "Il mercato è chiuso. Restano disponibili solo gli scambi tra squadre."
)


class LeagueMarketGate(Protocol):
    market_open: bool


def assert_market_open(league: LeagueMarketGate) -> None:
    """Block roster moves and auction activity while the admin switch is off."""
    if not league.market_open:
        raise ValidationAuthError(MARKET_CLOSED_MESSAGE, code=MARKET_CLOSED_CODE)
