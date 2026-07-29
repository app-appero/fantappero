"""League dependencies for FastAPI routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.deps_authorization import get_authorization_service
from app.deps_db import get_db
from authorization.service import AuthorizationService
from leagues.service import LeagueService


def get_league_service(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[AuthorizationService, Depends(get_authorization_service)],
) -> LeagueService:
    return LeagueService(db, authorization)
