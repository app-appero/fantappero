"""Authorization for running a live-auction session: admin or its delegate (EP08-09).

A live session's operator is scoped to that single session (``market_sessions.
operator_user_id``), not a league-wide role — deliberately not a new
``Permission`` value, to avoid touching the ``Permission``/``resolve_permissions``
pair that is otherwise kept in lockstep between this backend and the TS
contracts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from authorization.dependencies import require_league_permissions
from authorization.exceptions import ForbiddenError
from database.enums import LeagueRole, Permission
from market.models import MarketSession


def require_live_session_operator(
    session_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    db: Session = Depends(get_db_session),
) -> LeagueAccess:
    """League admin, or the delegate named on this specific session, may operate it."""
    if league_access.api_role == LeagueRole.LEAGUE_ADMIN or league_access.operator_bypass:
        return league_access

    market_session = db.scalar(
        select(MarketSession).where(
            MarketSession.id == session_id,
            MarketSession.league_id == league_access.league.id,
        )
    )
    if market_session is None:
        raise ValidationAuthError(
            "Sessione di mercato non trovata.",
            code="market_session_not_found",
        )
    if market_session.operator_user_id != league_access.user.id:
        raise ForbiddenError()
    return league_access
