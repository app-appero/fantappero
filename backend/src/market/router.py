"""HTTP routes for the sealed-bid initial auction session (EP08-01)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from authorization.context import LeagueAccess
from authorization.dependencies import require_league_permissions
from database.enums import MarketSessionKind, Permission
from market.schemas import (
    CreateMarketSessionRequest,
    MarketBidListResponse,
    MarketBidResponse,
    MarketReleasePreviewResponse,
    MarketReleaseRequest,
    MarketReleaseResultResponse,
    MarketResolutionResponse,
    MarketSessionResponse,
    SubmitMarketBidRequest,
)
from market.service import MarketService
from market.trade_schemas import (
    CounterTradeProposalRequest,
    CreateTradeProposalRequest,
    TradeProposalListResponse,
    TradeProposalResponse,
)
from market.trade_service import TradeService

router = APIRouter(prefix="/leagues", tags=["market"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "code": exc.code},
    )


def get_market_service(session: Session = Depends(get_db_session)) -> MarketService:
    return MarketService(session)


def get_trade_service(session: Session = Depends(get_db_session)) -> TradeService:
    return TradeService(session)


@router.post(
    "/{league_id}/mercato/asta/sessioni",
    response_model=MarketSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_auction_session(
    body: CreateMarketSessionRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: MarketService = Depends(get_market_service),
) -> MarketSessionResponse | JSONResponse:
    """Create the league's sealed-bid initial auction window (admin)."""
    try:
        return service.create_auction_session(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
    response_model=MarketSessionResponse,
)
def close_auction_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: MarketService = Depends(get_market_service),
) -> MarketSessionResponse | JSONResponse:
    """Close a session before its scheduled deadline (admin)."""
    try:
        return service.close_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/asta/sessioni/{session_id}/risolvi",
    response_model=MarketResolutionResponse,
)
def resolve_auction_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: MarketService = Depends(get_market_service),
) -> MarketResolutionResponse | JSONResponse:
    """Resolve a closed session: highest bid wins, ties reopen a tiebreak (admin)."""
    try:
        return service.resolve_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/asta/sessioni",
    response_model=list[MarketSessionResponse],
)
def list_auction_sessions(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> list[MarketSessionResponse]:
    """List auction sessions for the league (bid amounts stay sealed)."""
    return service.list_sessions(league_access, kind=MarketSessionKind.INITIAL_AUCTION)


@router.get(
    "/{league_id}/mercato/asta/sessioni/{session_id}",
    response_model=MarketSessionResponse,
)
def get_auction_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketSessionResponse | JSONResponse:
    try:
        return service.get_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete_id}",
    response_model=MarketBidResponse,
)
def submit_auction_bid(
    session_id: UUID,
    athlete_id: UUID,
    body: SubmitMarketBidRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketBidResponse | JSONResponse:
    """Submit or replace the caller's sealed bid for one athlete (own team)."""
    try:
        return service.submit_bid(league_access, session_id, athlete_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.delete(
    "/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def withdraw_auction_bid(
    session_id: UUID,
    athlete_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> None | JSONResponse:
    """Withdraw the caller's sealed bid before the session closes (own team)."""
    try:
        service.withdraw_bid(league_access, session_id, athlete_id)
        return None
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/asta/sessioni/{session_id}/offerte",
    response_model=MarketBidListResponse,
)
def list_my_auction_bids(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketBidListResponse | JSONResponse:
    """List the caller's own sealed bids for a session (own team only)."""
    try:
        return service.list_my_bids(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


# -- Mercato svincolati: sealed-bid waiver window (EP08-03 / FR-MKT-01) ----------
# Shares the same session/bid mechanics as the initial auction above; each waiver
# bid additionally names the roster player the team commits to release if it wins.


@router.post(
    "/{league_id}/mercato/svincoli/sessioni",
    response_model=MarketSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_waiver_session(
    body: CreateMarketSessionRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: MarketService = Depends(get_market_service),
) -> MarketSessionResponse | JSONResponse:
    """Create the league's sealed-bid waiver window (admin)."""
    try:
        return service.create_waiver_session(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/svincoli/sessioni/{session_id}/chiudi",
    response_model=MarketSessionResponse,
)
def close_waiver_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: MarketService = Depends(get_market_service),
) -> MarketSessionResponse | JSONResponse:
    """Close a waiver session before its scheduled deadline (admin)."""
    try:
        return service.close_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/svincoli/sessioni/{session_id}/risolvi",
    response_model=MarketResolutionResponse,
)
def resolve_waiver_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_MANAGE)),
    service: MarketService = Depends(get_market_service),
) -> MarketResolutionResponse | JSONResponse:
    """Resolve a closed waiver session: highest bid wins, ties reopen a tiebreak (admin)."""
    try:
        return service.resolve_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/svincoli/sessioni",
    response_model=list[MarketSessionResponse],
)
def list_waiver_sessions(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> list[MarketSessionResponse]:
    """List waiver sessions for the league (bid amounts stay sealed)."""
    return service.list_sessions(league_access, kind=MarketSessionKind.WAIVER)


@router.get(
    "/{league_id}/mercato/svincoli/sessioni/{session_id}",
    response_model=MarketSessionResponse,
)
def get_waiver_session(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketSessionResponse | JSONResponse:
    try:
        return service.get_session(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{athlete_id}",
    response_model=MarketBidResponse,
)
def submit_waiver_bid(
    session_id: UUID,
    athlete_id: UUID,
    body: SubmitMarketBidRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketBidResponse | JSONResponse:
    """Submit or replace the caller's sealed waiver bid, naming the release (own team)."""
    try:
        return service.submit_bid(league_access, session_id, athlete_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.delete(
    "/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte/{athlete_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def withdraw_waiver_bid(
    session_id: UUID,
    athlete_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> None | JSONResponse:
    """Withdraw the caller's sealed waiver bid before the session closes (own team)."""
    try:
        service.withdraw_bid(league_access, session_id, athlete_id)
        return None
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/svincoli/sessioni/{session_id}/offerte",
    response_model=MarketBidListResponse,
)
def list_my_waiver_bids(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketBidListResponse | JSONResponse:
    """List the caller's own sealed waiver bids for a session (own team only)."""
    try:
        return service.list_my_bids(league_access, session_id)
    except AuthError as exc:
        return _error_response(exc)


# -- Svincolo volontario e recupero crediti (EP08-04 / FR-MKT-02) ---------------


@router.get(
    "/{league_id}/mercato/svincolo/{slot_index}/anteprima",
    response_model=MarketReleasePreviewResponse,
)
def preview_voluntary_release(
    slot_index: int,
    reason: str = Query(alias="causa"),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketReleasePreviewResponse | JSONResponse:
    """Preview the credit refund for releasing the caller's own player before confirming."""
    try:
        return service.preview_release(league_access, slot_index, reason)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/svincolo/{slot_index}",
    response_model=MarketReleaseResultResponse,
)
def apply_voluntary_release(
    slot_index: int,
    body: MarketReleaseRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: MarketService = Depends(get_market_service),
) -> MarketReleaseResultResponse | JSONResponse:
    """Release the caller's own player and apply the percentage-based credit refund."""
    try:
        return service.apply_release(league_access, slot_index, body.reason)
    except AuthError as exc:
        return _error_response(exc)


# -- Scambi tra partecipanti: proposta (EP08-05 / FR-MKT-03) --------------------


@router.post(
    "/{league_id}/mercato/scambi/proposte",
    response_model=TradeProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trade_proposal(
    body: CreateTradeProposalRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: TradeService = Depends(get_trade_service),
) -> TradeProposalResponse | JSONResponse:
    """Propose a trade to another team in the league (own team as proposer)."""
    try:
        return service.create_proposal(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/scambi/proposte",
    response_model=TradeProposalListResponse,
)
def list_trade_proposals(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: TradeService = Depends(get_trade_service),
) -> TradeProposalListResponse | JSONResponse:
    """List trade proposals sent or received by the caller's team."""
    try:
        return service.list_proposals(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/mercato/scambi/proposte/{proposal_id}",
    response_model=TradeProposalResponse,
)
def get_trade_proposal(
    proposal_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: TradeService = Depends(get_trade_service),
) -> TradeProposalResponse | JSONResponse:
    try:
        return service.get_proposal(league_access, proposal_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/scambi/proposte/{proposal_id}/annulla",
    response_model=TradeProposalResponse,
)
def cancel_trade_proposal(
    proposal_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: TradeService = Depends(get_trade_service),
) -> TradeProposalResponse | JSONResponse:
    """Withdraw the caller's own pending proposal before the recipient acts on it."""
    try:
        return service.cancel_proposal(league_access, proposal_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/scambi/proposte/{proposal_id}/accetta",
    response_model=TradeProposalResponse,
)
def accept_trade_proposal(
    proposal_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: TradeService = Depends(get_trade_service),
) -> TradeProposalResponse | JSONResponse:
    """Accept a pending proposal (recipient only): re-validated and executed atomically."""
    try:
        return service.accept_proposal(league_access, proposal_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/scambi/proposte/{proposal_id}/rifiuta",
    response_model=TradeProposalResponse,
)
def reject_trade_proposal(
    proposal_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: TradeService = Depends(get_trade_service),
) -> TradeProposalResponse | JSONResponse:
    """Reject a pending proposal (recipient only)."""
    try:
        return service.reject_proposal(league_access, proposal_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/mercato/scambi/proposte/{proposal_id}/controproponi",
    response_model=TradeProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
def counter_trade_proposal(
    proposal_id: UUID,
    body: CounterTradeProposalRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    service: TradeService = Depends(get_trade_service),
) -> TradeProposalResponse | JSONResponse:
    """Counter a pending proposal (recipient only): flips proposer/recipient roles."""
    try:
        return service.counter_proposal(league_access, proposal_id, body)
    except AuthError as exc:
        return _error_response(exc)
