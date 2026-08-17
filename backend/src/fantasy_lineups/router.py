"""HTTP routes for fantasy lineups (EP06-02 / EP06-03 / EP06-04 / EP06-05 / EP06-06)."""

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
from fantasy_lineups.schemas import LineupContextResponse, SaveLineupDraftRequest, SaveLineupRequest
from fantasy_lineups.service import FantasyLineupService

router = APIRouter(prefix="/leagues", tags=["fantasy-lineups"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "code": exc.code},
    )


def get_fantasy_lineup_service(
    session: Session = Depends(get_db_session),
) -> FantasyLineupService:
    return FantasyLineupService(session)


@router.get(
    "/{league_id}/turni/{round_id}/formazione",
    response_model=LineupContextResponse,
)
def get_my_lineup(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Formazione del chiamante per il turno (moduli, rosa, lock per kickoff)."""
    try:
        return service.get_my_lineup(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/turni/{round_id}/formazione",
    response_model=LineupContextResponse,
)
def save_my_lineup(
    round_id: UUID,
    body: SaveLineupRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Salva la formazione se modulo, panchina e lock per-calciatore sono validi."""
    try:
        return service.save_my_lineup(league_access, round_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/turni/{round_id}/formazione/copia",
    response_model=LineupContextResponse,
)
def copy_previous_lineup_to_draft(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Copia la formazione precedente in bozza, rivalidata su rosa e lock correnti."""
    try:
        return service.copy_previous_to_draft(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/turni/{round_id}/formazione/bozza",
    response_model=LineupContextResponse,
)
def save_my_lineup_draft(
    round_id: UUID,
    body: SaveLineupDraftRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Salva una bozza incompleta senza confermare né consumare mosse tattiche."""
    try:
        return service.save_my_draft(league_access, round_id, body)
    except AuthError as exc:
        return _error_response(exc)
