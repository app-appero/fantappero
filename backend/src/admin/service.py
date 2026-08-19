"""Admin panel business logic — platform operator views (EP11-04a)."""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from admin.exceptions import AdminUserNotFoundError, LastOperatorRevokeError
from admin.schemas import (
    AdminLeagueResponse,
    AdminOverviewResponse,
    AdminUserResponse,
    PaginatedAdminLeaguesResponse,
    PaginatedAdminUsersResponse,
)
from auth.models.user import User
from auth.models.user_profile import UserProfile
from config.settings.api import ApiSettings
from database.enums import LeagueMemberRole, PlatformRole
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from observability.logging import get_logger

PAGE_SIZE = 20

_logger = get_logger(__name__)


def _escape_ilike(term: str) -> str:
    return term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=str(user.id),
        email=user.email,
        displayName=user.display_name,
        platformRole=user.platform_role,
        createdAt=user.created_at,
    )


def _total_pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


class AdminService:
    """Read-only platform views and operator role management (EP11-04a).

    Out of scope by design: no mutation of league rules, credits, moves or scores —
    only the operator role toggle and read-only listings needed for M1/M4.
    """

    def __init__(self, session: Session, settings: ApiSettings) -> None:
        self._session = session
        self._settings = settings

    def overview(self, operator: User) -> AdminOverviewResponse:
        users_count = self._session.scalar(select(func.count(User.id))) or 0
        operators_count = (
            self._session.scalar(
                select(func.count(User.id)).where(User.platform_role == PlatformRole.OPERATOR)
            )
            or 0
        )
        leagues_count = self._session.scalar(select(func.count(League.id))) or 0
        return AdminOverviewResponse(
            operatorId=str(operator.id),
            operatorDisplayName=operator.display_name,
            environment=self._settings.fantappero_env.value,
            usersCount=users_count,
            operatorsCount=operators_count,
            leaguesCount=leagues_count,
        )

    def list_users(
        self, *, query: str | None, page: int, page_size: int = PAGE_SIZE
    ) -> PaginatedAdminUsersResponse:
        base = select(User).outerjoin(UserProfile, UserProfile.user_id == User.id).where(
            User.deleted_at.is_(None)
        )
        if query:
            escaped = _escape_ilike(query)
            if escaped:
                base = base.where(
                    User.email.ilike(f"%{escaped}%", escape="\\")
                    | UserProfile.display_name.ilike(f"%{escaped}%", escape="\\")
                )
        total = (
            self._session.scalar(select(func.count()).select_from(base.order_by(None).subquery()))
            or 0
        )
        rows = self._session.scalars(
            base.options(selectinload(User.profile))
            .order_by(User.created_at.desc(), User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return PaginatedAdminUsersResponse(
            items=[_to_user_response(user) for user in rows],
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=_total_pages(total, page_size),
        )

    def promote_operator(self, *, actor: User, target_user_id: UUID) -> AdminUserResponse:
        user = self._get_user_or_raise(target_user_id)
        if user.platform_role != PlatformRole.OPERATOR:
            user.platform_role = PlatformRole.OPERATOR
            self._session.flush()
            _logger.info(
                "admin operator role changed",
                extra={
                    "event": "admin_operator_promoted",
                    "actor_id": str(actor.id),
                    "target_user_id": str(user.id),
                },
            )
        return _to_user_response(user)

    def revoke_operator(self, *, actor: User, target_user_id: UUID) -> AdminUserResponse:
        user = self._get_user_or_raise(target_user_id)
        if user.platform_role == PlatformRole.OPERATOR:
            operators_count = (
                self._session.scalar(
                    select(func.count(User.id)).where(User.platform_role == PlatformRole.OPERATOR)
                )
                or 0
            )
            if operators_count <= 1:
                raise LastOperatorRevokeError()
            user.platform_role = PlatformRole.USER
            self._session.flush()
            _logger.info(
                "admin operator role changed",
                extra={
                    "event": "admin_operator_revoked",
                    "actor_id": str(actor.id),
                    "target_user_id": str(user.id),
                },
            )
        return _to_user_response(user)

    def list_leagues(
        self, *, query: str | None, page: int, page_size: int = PAGE_SIZE
    ) -> PaginatedAdminLeaguesResponse:
        base = select(League)
        if query:
            escaped = _escape_ilike(query)
            if escaped:
                base = base.where(League.name.ilike(f"%{escaped}%", escape="\\"))
        total = (
            self._session.scalar(select(func.count()).select_from(base.order_by(None).subquery()))
            or 0
        )
        leagues = self._session.scalars(
            base.order_by(League.created_at.desc(), League.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        owners: dict[UUID, User] = {}
        league_ids = [league.id for league in leagues]
        if league_ids:
            owner_rows = self._session.execute(
                select(LeagueMembership.league_id, User)
                .join(User, User.id == LeagueMembership.user_id)
                .options(selectinload(User.profile))
                .where(
                    LeagueMembership.league_id.in_(league_ids),
                    LeagueMembership.role == LeagueMemberRole.OWNER,
                )
            ).all()
            owners = {league_id: user for league_id, user in owner_rows}

        items = [
            AdminLeagueResponse(
                id=str(league.id),
                name=league.name,
                state=league.state,
                ownerDisplayName=owners[league.id].display_name if league.id in owners else None,
                createdAt=league.created_at,
            )
            for league in leagues
        ]
        return PaginatedAdminLeaguesResponse(
            items=items,
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=_total_pages(total, page_size),
        )

    def _get_user_or_raise(self, user_id: UUID) -> User:
        user = self._session.get(User, user_id)
        if user is None or user.deleted_at is not None:
            raise AdminUserNotFoundError()
        return user
