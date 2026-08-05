"""League membership lookups for authorization (EP02-03)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from auth.models.user import User
from authorization.context import LeagueAccess
from authorization.exceptions import LeagueAccessDeniedError, LeagueNotFoundError
from database.enums import PlatformRole
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from observability.metrics import get_metrics


class AuthorizationService:
    """Resolve tenant membership and enforce league boundaries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_league(self, league_id: UUID) -> League | None:
        return self._session.get(League, league_id)

    def get_membership(self, *, user_id: UUID, league_id: UUID) -> LeagueMembership | None:
        stmt = select(LeagueMembership).where(
            LeagueMembership.user_id == user_id,
            LeagueMembership.league_id == league_id,
        )
        return self._session.scalars(stmt).first()

    def list_memberships_for_user(self, user_id: UUID) -> list[LeagueMembership]:
        stmt = (
            select(LeagueMembership)
            .where(LeagueMembership.user_id == user_id)
            .options(joinedload(LeagueMembership.league))
            .order_by(LeagueMembership.created_at.asc())
        )
        return list(self._session.scalars(stmt).unique().all())

    def resolve_league_access(self, user: User, league_id: UUID) -> LeagueAccess:
        league = self.get_league(league_id)
        if league is None:
            get_metrics().incr(
                "authorization_denied_total",
                labels={"reason": "league_not_found"},
            )
            raise LeagueNotFoundError()

        membership = self.get_membership(user_id=user.id, league_id=league_id)
        if membership is not None:
            return LeagueAccess(league=league, user=user, membership_role=membership.role)

        if user.platform_role == PlatformRole.OPERATOR:
            return LeagueAccess(
                league=league,
                user=user,
                membership_role=None,
                operator_bypass=True,
            )

        get_metrics().incr(
            "authorization_denied_total",
            labels={"reason": "league_access_denied"},
        )
        raise LeagueAccessDeniedError()
