"""League routes with membership and role policies (EP02-03, EP03-01)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.deps_auth import get_current_user
from app.deps_league import get_league_service
from database.models.accounts import User
from leagues.schemas import (
    CompetitionResponse,
    CreateLeagueRequest,
    LeagueResponse,
    UpdateLeagueRequest,
)
from leagues.service import LeagueService

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/competitions", response_model=list[CompetitionResponse])
def list_competitions(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LeagueService, Depends(get_league_service)],
) -> list[CompetitionResponse]:
    _ = user
    return service.list_competitions()


@router.post("", response_model=LeagueResponse, status_code=201)
def create_league(
    body: CreateLeagueRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LeagueService, Depends(get_league_service)],
) -> LeagueResponse:
    correlation_id = request.headers.get("X-Correlation-ID")
    return service.create_league(owner=user, body=body, correlation_id=correlation_id)


@router.get("/{league_id}", response_model=LeagueResponse)
def get_league(
    league_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LeagueService, Depends(get_league_service)],
) -> LeagueResponse:
    return service.get_league(actor=user, league_id=league_id)


@router.patch("/{league_id}", response_model=LeagueResponse)
def update_league(
    league_id: uuid.UUID,
    body: UpdateLeagueRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LeagueService, Depends(get_league_service)],
) -> LeagueResponse:
    return service.update_league(actor=user, league_id=league_id, name=body.name)
