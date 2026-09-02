"""Atomic league participant management (EP03-04)."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    LeagueMemberRole,
    league_member_role_to_league_role,
)
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.schemas import LeagueMemberResponse
from leagues.validators import (
    validate_admin_transfer_target,
    validate_configurable_league_state,
    validate_member_removal,
)
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


class LeagueMembershipService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, league_access: LeagueAccess) -> list[LeagueMemberResponse]:
        memberships = self._load_memberships(league_access.league.id)
        return [self._to_response(membership) for membership in memberships]

    def remove(
        self,
        league_access: LeagueAccess,
        target_user_id: UUID,
    ) -> LeagueMemberResponse:
        league = self._lock_league(league_access.league.id)
        self._require_configurable(league, metric="league_member_removed_total")
        membership = self._get_membership(league.id, target_user_id)
        if membership is None:
            self._fail(
                "Partecipante non trovato.",
                code="member_not_found",
                metric="league_member_removed_total",
                result="not_found",
            )

        try:
            validate_member_removal(membership.role)
        except ValidationAuthError:
            get_metrics().incr(
                "league_member_removed_total",
                labels={"result": "cannot_remove_admin"},
            )
            raise

        response = self._to_response(membership)
        self._session.delete(membership)
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.LEAGUE_MEMBER_REMOVED,
        )
        self._session.commit()
        get_metrics().incr("league_member_removed_total", labels={"result": "success"})
        logger.info("league_member_removed", extra={"result": "success"})
        return response

    def transfer_admin(
        self,
        league_access: LeagueAccess,
        target_user_id: UUID,
    ) -> LeagueMemberResponse:
        league = self._lock_league(league_access.league.id)
        self._require_configurable(league, metric="league_admin_transferred_total")
        memberships = self._load_memberships(league.id, for_update=True)
        owner = next(
            (row for row in memberships if row.role == LeagueMemberRole.OWNER),
            None,
        )
        target = next((row for row in memberships if row.user_id == target_user_id), None)
        if target is None:
            self._fail(
                "Partecipante non trovato.",
                code="member_not_found",
                metric="league_admin_transferred_total",
                result="not_found",
            )
        if owner is None:
            self._fail(
                "La lega deve avere un amministratore.",
                code="league_admin_required",
                metric="league_admin_transferred_total",
                result="admin_missing",
            )
        if target.id == owner.id:
            get_metrics().incr("league_admin_transferred_total", labels={"result": "noop"})
            return self._to_response(target)

        try:
            validate_admin_transfer_target(target.role)
        except ValidationAuthError:
            get_metrics().incr(
                "league_admin_transferred_total",
                labels={"result": "invalid_target"},
            )
            raise

        owner.role = LeagueMemberRole.MEMBER
        target.role = LeagueMemberRole.OWNER
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.LEAGUE_ADMIN_TRANSFERRED,
        )
        self._session.commit()
        get_metrics().incr("league_admin_transferred_total", labels={"result": "success"})
        logger.info("league_admin_transferred", extra={"result": "success"})
        return self._to_response(target)

    def _load_memberships(
        self,
        league_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[LeagueMembership]:
        statement = (
            select(LeagueMembership)
            .where(LeagueMembership.league_id == league_id)
            .options(selectinload(LeagueMembership.user).selectinload(User.profile))
            .order_by(LeagueMembership.created_at.asc(), LeagueMembership.id.asc())
        )
        if for_update:
            statement = statement.with_for_update()
        return list(self._session.scalars(statement).all())

    def _get_membership(
        self,
        league_id: UUID,
        user_id: UUID,
    ) -> LeagueMembership | None:
        return self._session.scalars(
            select(LeagueMembership)
            .where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.user_id == user_id,
            )
            .options(selectinload(LeagueMembership.user).selectinload(User.profile))
            .with_for_update()
        ).first()

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League).where(League.id == league_id).with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

    @staticmethod
    def _require_configurable(league: League, *, metric: str) -> None:
        try:
            validate_configurable_league_state(league.state, subject="i partecipanti")
        except ValidationAuthError:
            get_metrics().incr(metric, labels={"result": "league_not_draft"})
            raise

    def _add_audit(
        self,
        league_id: UUID,
        actor_id: UUID,
        action: LeagueAuditAction,
    ) -> None:
        self._session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=actor_id,
                action=action,
                correlation_id=get_correlation_id(),
            )
        )

    @staticmethod
    def _to_response(membership: LeagueMembership) -> LeagueMemberResponse:
        return LeagueMemberResponse(
            userId=str(membership.user_id),
            displayName=membership.user.display_name,
            userType=membership.user.user_type.value,
            role=league_member_role_to_league_role(membership.role).value,
            joinedAt=membership.created_at,
        )

    @staticmethod
    def _fail(
        message: str,
        *,
        code: str,
        metric: str,
        result: str,
    ) -> NoReturn:
        get_metrics().incr(metric, labels={"result": result})
        raise ValidationAuthError(message, code=code)
