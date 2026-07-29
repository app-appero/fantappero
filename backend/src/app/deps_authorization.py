"""Authorization dependencies for FastAPI routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.deps_db import get_db
from authorization.service import AuthorizationService


def get_authorization_service(
    db: Annotated[Session, Depends(get_db)],
) -> AuthorizationService:
    return AuthorizationService(db)
