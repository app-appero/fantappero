"""Privacy dependencies for FastAPI routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.deps_auth import get_auth_service
from app.deps_authorization import get_authorization_service
from app.deps_db import get_db
from auth.service import AuthService
from authorization.service import AuthorizationService
from privacy.service import PrivacyService


def get_privacy_service(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[AuthorizationService, Depends(get_authorization_service)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> PrivacyService:
    return PrivacyService(db, authorization, auth)
