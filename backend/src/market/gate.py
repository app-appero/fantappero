"""League-admin market window: rosa and auctions vs always-on trades.

Decisione del 20/11/2026: l'attività di mercato richiede tre condizioni insieme, la lega al
completo (``leagues.capacity``), l'interruttore dell'amministratore acceso e nessun turno in
corso (``market.round_freeze``). Gli scambi ignorano l'interruttore ma non le altre due.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, object_session
from sqlalchemy.orm.exc import UnmappedInstanceError

from auth.exceptions import ValidationAuthError

MARKET_CLOSED_CODE = "market_closed"
MARKET_CLOSED_MESSAGE = "Il mercato è chiuso. Restano disponibili solo gli scambi tra squadre."

MarketBlockedReason = Literal["league_not_full", "market_closed", "round_in_progress"]


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


def assert_market_open(league: LeagueMarketGate, *, actor_is_admin: bool = False) -> None:
    """Block roster moves and auction activity while the market cannot run.

    Prima la lega al completo, poi l'interruttore, poi il turno in corso: a lega incompleta
    l'errore è ``league_not_full`` anche a interruttore spento, perché è la condizione che
    l'amministratore deve risolvere per primo.

    ``actor_is_admin`` è per le operazioni dell'amministratore sulle rose (assegnazioni e
    sostituzioni, rettifiche di prezzo, svincoli, import CSV/Excel, rosa random IA): decisione
    del 20/11, l'amministratore prepara le rose in anticipo, quindi per lui non contano né la
    lega al completo né l'interruttore, solo il turno in corso. Aste e svincolati non lo
    passano mai: sono attività di mercato per tutti, amministratore compreso.
    """
    league_id = getattr(league, "id", None)
    try:
        session = object_session(league)
    except UnmappedInstanceError:
        session = None
    if not actor_is_admin:
        if session is not None and league_id is not None:
            from leagues.capacity import assert_league_full_for_market

            assert_league_full_for_market(session, league_id)
        if not _league_is_open(league):
            raise ValidationAuthError(MARKET_CLOSED_MESSAGE, code=MARKET_CLOSED_CODE)
    if session is not None and league_id is not None:
        from market.round_freeze import assert_no_round_in_progress

        assert_no_round_in_progress(session, league_id)


def assert_trade_market_open(session: Session, league_id: UUID) -> None:
    """Scambi: lega al completo e nessun turno in corso (l'interruttore non conta)."""
    from leagues.capacity import assert_league_full_for_market
    from market.round_freeze import assert_no_round_in_progress

    assert_league_full_for_market(session, league_id)
    assert_no_round_in_progress(session, league_id)


@dataclass(frozen=True, slots=True)
class MarketStatus:
    """Stato del mercato per le app: interruttore, posti occupati e motivo del blocco.

    ``pending_invite_count`` sono gli inviti nominativi che tengono un posto (in attesa, non
    scaduti): le app li mostrano accanto al conto, ma la lega è al completo solo con gli iscritti.
    """

    market_open: bool
    member_count: int
    participant_count: int | None
    league_full: bool
    blocked_reason: MarketBlockedReason | None
    pending_invite_count: int = 0


def market_status(session: Session, league_id: UUID) -> MarketStatus:
    from leagues.capacity import league_occupancy
    from leagues.market_open import read_market_open
    from market.round_freeze import league_round_in_progress

    occupancy = league_occupancy(session, league_id)
    market_open = read_market_open(session, league_id)
    reason: MarketBlockedReason | None
    if not occupancy.is_full:
        reason = "league_not_full"
    elif not market_open:
        reason = "market_closed"
    elif league_round_in_progress(session, league_id) is not None:
        reason = "round_in_progress"
    else:
        reason = None
    return MarketStatus(
        market_open=market_open,
        member_count=occupancy.members,
        participant_count=occupancy.participants,
        league_full=occupancy.is_full,
        blocked_reason=reason,
        pending_invite_count=occupancy.pending_invites,
    )
