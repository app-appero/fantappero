"""HTTP routes for the live/ascending auction mode (EP08-09).

Distinct path prefix (``/mercato/asta-live/...``) from the sealed-bid
``/mercato/asta/...`` router — the two are independent, never share a route.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from authorization.context import LeagueAccess
from authorization.dependencies import require_league_permissions
from database.enums import Permission
from market.live_authorization import require_live_session_operator
from market.live_schemas import (
    ConfigureLiveAuctionSessionRequest,
    CreateLiveAuctionSessionRequest,
    LiveAuctionSessionResponse,
    LiveLotListResponse,
    LiveLotResponse,
    LiveLotStateResponse,
    NominateLotRequest,
    PlaceRaiseRequest,
    ResolveSwapRequest,
)
from market.live_service import LiveMarketService

router = APIRouter(prefix="/leagues", tags=["market-live"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "code": exc.code},
    )


def get_live_market_service(session: Session = Depends(get_db_session)) -> LiveMarketService:
    return LiveMarketService(session)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni",
    response_model=LiveAuctionSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_live_auction_session(
    body: CreateLiveAuctionSessionRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveAuctionSessionResponse | JSONResponse:
    """Create a live-auction session for the league's initial auction (admin)."""
    try:
        return service.create_session(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/configurazione",
    response_model=LiveAuctionSessionResponse,
)
def configure_live_auction_session(
    session_id: UUID,
    body: ConfigureLiveAuctionSessionRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveAuctionSessionResponse | JSONResponse:
    """Reconfigure increments/timers/operator/queue while still scheduled (admin)."""
    try:
        return service.configure_session(league_access, session_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/asta-live/sessioni",
    response_model=list[LiveAuctionSessionResponse],
)
def list_live_auction_sessions(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> list[LiveAuctionSessionResponse]:
    """List live-auction sessions for the league."""
    return service.list_sessions(league_access)


@router.get(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}",
    response_model=LiveAuctionSessionResponse,
)
def get_live_auction_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveAuctionSessionResponse | JSONResponse:
    try:
        return service.get_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/avvia",
    response_model=LiveAuctionSessionResponse,
)
def start_live_auction_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_live_session_operator),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveAuctionSessionResponse | JSONResponse:
    """Open the session to bidding (league admin or the session's delegate)."""
    try:
        return service.start_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/termina",
    response_model=LiveAuctionSessionResponse,
)
def end_live_auction_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_live_session_operator),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveAuctionSessionResponse | JSONResponse:
    """End the session once no lot is open (league admin or the session's delegate)."""
    try:
        return service.end_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
    response_model=LiveLotResponse,
    status_code=status.HTTP_201_CREATED,
)
def nominate_live_auction_lot(
    session_id: UUID,
    body: NominateLotRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotResponse | JSONResponse:
    """Open the next lot.

    Who may call it depends on the session's ``nominationMode``: the admin or
    delegate chooses the athlete (``manual``) or triggers the next queue entry
    (``sequential`` / ``alphabetical_by_role`` / ``random``); in ``turn_based``
    the fantasy team whose turn it is may also call, naming the athlete — the
    admin/delegate can still call on anyone's behalf. Fine-grained "whose turn
    is it" enforcement lives in ``LiveMarketService.nominate_lot``.
    """
    try:
        return service.nominate_lot(league_access, session_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
    response_model=LiveLotResponse,
)
def place_live_auction_raise(
    session_id: UUID,
    lot_id: UUID,
    body: PlaceRaiseRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotResponse | JSONResponse:
    """Place a raise on the open lot (own team)."""
    try:
        return service.place_raise(league_access, session_id, lot_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/aggiudica",
    response_model=LiveLotResponse,
)
def force_sell_live_auction_lot(
    session_id: UUID,
    lot_id: UUID,
    league_access: LeagueAccess = Depends(require_live_session_operator),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotResponse | JSONResponse:
    """Force-sell the lot to its current leader now (league admin or delegate)."""
    try:
        return service.force_sell_lot(league_access, session_id, lot_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/salta",
    response_model=LiveLotResponse,
)
def pass_live_auction_lot(
    session_id: UUID,
    lot_id: UUID,
    league_access: LeagueAccess = Depends(require_live_session_operator),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotResponse | JSONResponse:
    """Pass the lot: no assignment (league admin or delegate)."""
    try:
        return service.pass_lot(league_access, session_id, lot_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/annulla",
    response_model=LiveLotResponse,
)
def cancel_live_auction_lot(
    session_id: UUID,
    lot_id: UUID,
    league_access: LeagueAccess = Depends(require_live_session_operator),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotResponse | JSONResponse:
    """Void a mis-nomination before any raise was placed (league admin or delegate)."""
    try:
        return service.cancel_lot(league_access, session_id, lot_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/scambia",
    response_model=LiveLotResponse,
)
def resolve_live_auction_swap(
    session_id: UUID,
    lot_id: UUID,
    body: ResolveSwapRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotResponse | JSONResponse:
    """Resolve a roster-full swap prompt (own team only, not an operator action)."""
    try:
        return service.resolve_swap(league_access, session_id, lot_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rinuncia-scambio",
    response_model=LiveLotResponse,
)
def decline_live_auction_swap(
    session_id: UUID,
    lot_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotResponse | JSONResponse:
    """Decline a roster-full swap prompt: the lot is lost, no charge (own team only)."""
    try:
        return service.decline_swap(league_access, session_id, lot_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
    response_model=LiveLotStateResponse,
)
def get_live_auction_state(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotStateResponse | JSONResponse:
    """Poll endpoint: current lot, recent raises, seconds remaining."""
    try:
        return service.get_state(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti",
    response_model=LiveLotListResponse,
)
def list_live_auction_lots(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: LiveMarketService = Depends(get_live_market_service),
) -> LiveLotListResponse | JSONResponse:
    """Full lot history for the session (sold/passed/cancelled log)."""
    try:
        return service.list_lots(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)
