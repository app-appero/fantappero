"""FastAPI dependencies for authorization policies (EP02-03)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, get_db_session
from auth.models.user import User
from authorization.context import LeagueAccess, PermissionContext
from authorization.exceptions import ForbiddenError
from authorization.permissions import has_permissions
from authorization.service import AuthorizationService
from database.enums import Permission
from observability.metrics import get_metrics


def get_authorization_service(session: Session = Depends(get_db_session)) -> AuthorizationService:
    return AuthorizationService(session)


def require_permissions(*required: Permission) -> Callable[..., User]:
    """Require global/league-agnostic permissions (e.g. profile endpoints)."""

    required_tuple = tuple(required)

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        context = PermissionContext.for_user(current_user)
        if not has_permissions(context, required_tuple):
            get_metrics().incr(
                "authorization_denied_total",
                labels={"reason": "forbidden", "permission": required_tuple[0].value},
            )
            raise ForbiddenError()
        return current_user

    return _dependency


def require_league_permissions(*required: Permission) -> Callable[..., LeagueAccess]:
    """Require permissions within a league tenant (path ``league_id``)."""

    required_tuple = tuple(required)

    def _dependency(
        league_id: UUID,
        current_user: User = Depends(get_current_user),
        authz: AuthorizationService = Depends(get_authorization_service),
    ) -> LeagueAccess:
        league_access = authz.resolve_league_access(current_user, league_id)
        context = PermissionContext.for_user(current_user, league_access=league_access)
        if not has_permissions(context, required_tuple):
            get_metrics().incr(
                "authorization_denied_total",
                labels={"reason": "forbidden", "permission": required_tuple[0].value},
            )
            raise ForbiddenError()
        return league_access

    return _dependency
