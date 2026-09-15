"""League-admin market window: rosa and auctions vs always-on trades."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import object_session
from sqlalchemy.orm.exc import UnmappedInstanceError

from auth.exceptions import ValidationAuthError

MARKET_CLOSED_CODE = "market_closed"
MARKET_CLOSED_MESSAGE = (
    "Il mercato è chiuso. Restano disponibili solo gli scambi tra squadre."
)


class LeagueMarketGate(Protocol):
    market_open: bool


def _league_is_open(league: LeagueMarketGate) -> bool:
    """Resolve the flag; a missing ``market_open`` column counts as open."""
    league_id = getattr(league, "id", None)
    try:
        session = object_session(league)
    except UnmappedInstanceError:
        session = None
    if session is not None and league_id is not None:
        from leagues.market_open import read_market_open

        return read_market_open(session, league_id)
    try:
        return bool(league.market_open)
    except ProgrammingError:
        try:
            session = object_session(league)
        except UnmappedInstanceError:
            session = None
        if session is not None:
            session.rollback()
        return True


def assert_market_open(league: LeagueMarketGate) -> None:
    """Block roster moves and auction activity while the admin switch is off."""
    if not _league_is_open(league):
        raise ValidationAuthError(MARKET_CLOSED_MESSAGE, code=MARKET_CLOSED_CODE)
