"""API operatore per il voto statistico versionato (EP07-01)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.models.user import User
from authorization.dependencies import require_permissions
from database.enums import Permission
from fantasy_ratings.exceptions import FantasyRatingError
from fantasy_ratings.schemas import (
    ComputeRatingsRequest,
    ComputeRatingsResponse,
    PlayerMatchRatingResponse,
)
from fantasy_ratings.service import FantasyRatingService

router = APIRouter(prefix="/fantasy-ratings", tags=["fantasy-ratings"])


def get_rating_service(session: Session = Depends(get_db_session)) -> FantasyRatingService:
    return FantasyRatingService(session)


@router.post("/compute", response_model=ComputeRatingsResponse)
def compute_fixture_ratings_endpoint(
    body: ComputeRatingsRequest,
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: FantasyRatingService = Depends(get_rating_service),
) -> ComputeRatingsResponse:
    """Calcola i voti statistici di una partita (idempotente, atomico)."""
    return service.compute_for_fixture(
        fixture_id=body.fixture_id,
        fixture_provider_id=body.fixture_provider_id,
        league_id=body.league_id,
        minutes_threshold=body.minutes_threshold,
    )


@router.get("/fixtures/{fixture_id}", response_model=list[PlayerMatchRatingResponse])
def list_fixture_ratings(
    fixture_id: UUID,
    league_id: UUID | None = Query(default=None, alias="leagueId"),
    minutes_threshold: int | None = Query(default=None, alias="minutesThreshold"),
    _operator: User = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    service: FantasyRatingService = Depends(get_rating_service),
) -> list[PlayerMatchRatingResponse]:
    """Elenco voti persistiti: formula, input e componenti per ogni calciatore."""
    return service.list_for_fixture(
        fixture_id,
        league_id=league_id,
        minutes_threshold=minutes_threshold,
    )


def rating_error_handler(_request: object, exc: FantasyRatingError) -> JSONResponse:
    status_code = 404 if exc.code.endswith("not_found") else 400
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )
