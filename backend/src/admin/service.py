"""Admin panel business logic — platform operator views (EP11-04a)."""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from admin.exceptions import (
    AdminUserNotFoundError,
    CannotDeleteSelfError,
    CannotImpersonateSelfError,
    CannotModifyOperatorError,
    LastOperatorRevokeError,
    ProtectedOperatorError,
)
from admin.schemas import (
    AdminBlockedAccountResponse,
    AdminBlocklistResponse,
    AdminDeleteUserResponse,
    AdminImpersonateResponse,
    AdminLeagueResponse,
    AdminOverviewResponse,
    AdminTesterResponse,
    AdminTestModeResponse,
    AdminUserResponse,
    PaginatedAdminLeaguesResponse,
    PaginatedAdminUsersResponse,
)
from auth.blocklist import BlockList
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.privacy_service import PrivacyService
from auth.schemas import SessionUserResponse
from auth.security import create_access_token
from auth.tester_access import TesterAccess
from config.settings.api import ApiSettings
from database.enums import (
    LeagueAuditAction,
    LeagueMemberRole,
    PlatformRole,
    platform_role_to_global_role,
)
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from observability.logging import get_logger

PAGE_SIZE = 20

_logger = get_logger(__name__)


def _escape_ilike(term: str) -> str:
    return term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_user_response(
    user: User,
    tester_emails: frozenset[str] | set[str] | None = None,
    protected_emails: frozenset[str] | None = None,
) -> AdminUserResponse:
    is_tester = user.platform_role == PlatformRole.OPERATOR or (
        tester_emails is not None and user.email.strip().lower() in tester_emails
    )
    return AdminUserResponse(
        id=str(user.id),
        email=user.email,
        displayName=user.display_name,
        platformRole=user.platform_role,
        createdAt=user.created_at,
        isTester=is_tester,
        isProtected=(
            protected_emails is not None
            and user.platform_role == PlatformRole.OPERATOR
            and user.email.strip().lower() in protected_emails
        ),
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
        base = (
            select(User)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.deleted_at.is_(None))
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
        tester_emails = TesterAccess(self._session).listed_emails()
        rows = self._session.scalars(
            base.options(selectinload(User.profile))
            .order_by(User.created_at.desc(), User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return PaginatedAdminUsersResponse(
            items=[
                _to_user_response(user, tester_emails, self._protected_emails()) for user in rows
            ],
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=_total_pages(total, page_size),
        )

    def _protected_emails(self) -> frozenset[str]:
        return self._settings.protected_operator_email_set()

    def _is_protected(self, user: User) -> bool:
        return user.email.strip().lower() in self._protected_emails()

    # --- eliminazione utente e lista nera ----------------------------------------------------
    def delete_user(
        self, *, actor: User, target_user_id: UUID, block: bool = True
    ) -> AdminDeleteUserResponse:
        """Elimina (anonimizza) un utente; con `block` ne mette l'email in lista nera."""
        user = self._get_user_or_raise(target_user_id)
        if user.id == actor.id:
            raise CannotDeleteSelfError()
        if self._is_protected(user):
            raise ProtectedOperatorError()
        if user.platform_role == PlatformRole.OPERATOR:
            raise CannotModifyOperatorError()
        # Prima il blocco dell'indirizzo originale, poi l'anonimizzazione (che lo sostituisce).
        email = user.email
        if block:
            BlockList(self._session).add(
                email, reason="Account eliminato dall'operatore", actor_id=actor.id
            )
        PrivacyService(self._session, self._settings).delete_account_by_operator(actor, user.id)
        _logger.info(
            "admin_user_deleted_and_blocked",
            extra={"actor_id": str(actor.id), "target_user_id": str(target_user_id)},
        )
        return AdminDeleteUserResponse(
            deletedUserId=str(target_user_id), blockedEmail=email if block else None
        )

    def blocklist(self) -> AdminBlocklistResponse:
        return AdminBlocklistResponse(
            items=[
                AdminBlockedAccountResponse(
                    id=str(entry.id),
                    email=entry.email,
                    reason=entry.reason,
                    createdAt=entry.created_at,
                )
                for entry in BlockList(self._session).list_entries()
            ]
        )

    def add_blocked(self, *, actor: User, email: str, reason: str | None) -> AdminBlocklistResponse:
        normalized = email.strip().lower()
        if normalized in self._protected_emails():
            raise ProtectedOperatorError()
        existing_operator = self._session.scalar(
            select(User.id).where(
                User.email == normalized,
                User.deleted_at.is_(None),
                User.platform_role == PlatformRole.OPERATOR,
            )
        )
        if existing_operator is not None:
            raise CannotModifyOperatorError()
        BlockList(self._session).add(email, reason=reason, actor_id=actor.id)
        self._session.commit()
        return self.blocklist()

    def remove_blocked(self, *, actor: User, entry_id: UUID) -> AdminBlocklistResponse:
        BlockList(self._session).remove(entry_id)
        self._session.commit()
        _logger.info(
            "admin_blocklist_entry_removed",
            extra={"actor_id": str(actor.id), "entry_id": str(entry_id)},
        )
        return self.blocklist()

    # --- modalità test (accesso riservato ai tester) -----------------------------------------
    def test_mode_state(self) -> AdminTestModeResponse:
        access = TesterAccess(self._session)
        entries = access.list_entries()
        names = {
            email: name
            for email, name in self._session.execute(
                select(User.email, UserProfile.display_name)
                .outerjoin(UserProfile, UserProfile.user_id == User.id)
                .where(User.deleted_at.is_(None))
            ).all()
        }
        return AdminTestModeResponse(
            enabled=access.is_test_mode(),
            testers=[
                AdminTesterResponse(
                    id=str(entry.id),
                    email=entry.email,
                    displayName=names.get(entry.email),
                    createdAt=entry.created_at,
                )
                for entry in entries
            ],
        )

    def set_test_mode(self, *, actor: User, enabled: bool) -> AdminTestModeResponse:
        TesterAccess(self._session).set_test_mode(enabled)
        self._audit_test_mode(actor, "test_mode_on" if enabled else "test_mode_off", {})
        self._session.commit()
        return self.test_mode_state()

    def add_tester(self, *, actor: User, email: str) -> AdminTestModeResponse:
        entry = TesterAccess(self._session).add(email, actor_id=actor.id)
        self._audit_test_mode(actor, "tester_added", {"testerId": str(entry.id)})
        self._session.commit()
        return self.test_mode_state()

    def remove_tester(self, *, actor: User, tester_id: UUID) -> AdminTestModeResponse:
        TesterAccess(self._session).remove(tester_id)
        self._audit_test_mode(actor, "tester_removed", {"testerId": str(tester_id)})
        self._session.commit()
        return self.test_mode_state()

    def _audit_test_mode(self, actor: User, event: str, details: dict[str, str]) -> None:
        _logger.info(
            "admin_test_mode_changed", extra={"event": event, "actor_id": str(actor.id), **details}
        )

    def promote_operator(self, *, actor: User, target_user_id: UUID) -> AdminUserResponse:
        user = self._get_user_or_raise(target_user_id)
        if user.platform_role != PlatformRole.OPERATOR:
            user.platform_role = PlatformRole.OPERATOR
            self._session.flush()
            self._session.add(
                LeagueAuditEvent(
                    league_id=None,
                    actor_id=actor.id,
                    action=LeagueAuditAction.PLATFORM_OPERATOR_PROMOTED,
                    details={"targetUserId": str(user.id)},
                )
            )
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
        if self._is_protected(user):
            raise ProtectedOperatorError()
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
            self._session.add(
                LeagueAuditEvent(
                    league_id=None,
                    actor_id=actor.id,
                    action=LeagueAuditAction.PLATFORM_OPERATOR_REVOKED,
                    details={"targetUserId": str(user.id)},
                )
            )
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

    def impersonate(self, *, actor: User, target_user_id: UUID) -> AdminImpersonateResponse:
        """Issue a short-lived, access-only token for ``target_user_id`` (support tool).

        No refresh token is issued and no `AuthSession` row is created: the
        impersonated session expires on its own after
        `jwt_access_token_expire_minutes`, exactly like a normal access token,
        and cannot be silently renewed. Operators can target other operators
        too (EP-operatore-test) — only impersonating yourself is blocked.
        Every start is audited (`league_id=None`, same pattern as
        promote/revoke) — there is no "end" event since the token simply
        expires.
        """
        user = self._get_user_or_raise(target_user_id)
        if user.id == actor.id:
            raise CannotImpersonateSelfError()

        access_token, expires_in = create_access_token(
            user_id=user.id,
            secret=self._settings.resolved_jwt_secret(),
            expire_minutes=self._settings.jwt_access_token_expire_minutes,
        )
        self._session.add(
            LeagueAuditEvent(
                league_id=None,
                actor_id=actor.id,
                action=LeagueAuditAction.USER_IMPERSONATION_STARTED,
                details={"targetUserId": str(user.id)},
            )
        )
        self._session.flush()
        _logger.info(
            "admin user impersonation started",
            extra={
                "event": "admin_user_impersonation_started",
                "actor_id": str(actor.id),
                "target_user_id": str(user.id),
            },
        )
        return AdminImpersonateResponse(
            accessToken=access_token,
            expiresIn=expires_in,
            user=SessionUserResponse(
                id=str(user.id),
                displayName=user.display_name,
                globalRole=platform_role_to_global_role(user.platform_role).value,
            ),
        )

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
