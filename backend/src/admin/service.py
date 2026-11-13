"""Admin panel business logic — platform operator views (EP11-04a)."""

from __future__ import annotations

import math
import secrets
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
    AdminImpersonationRevokeResponse,
    AdminLeagueResponse,
    AdminOverviewResponse,
    AdminTesterRequestListResponse,
    AdminTesterRequestResponse,
    AdminTesterResponse,
    AdminTestModeResponse,
    AdminUserResponse,
    PaginatedAdminLeaguesResponse,
    PaginatedAdminUsersResponse,
)
from auth.blocklist import BlockList
from auth.impersonation import ImpersonationStore
from auth.models.tester_request import TesterAccessRequest
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.privacy_service import PrivacyService
from auth.schemas import SessionUserResponse
from auth.security import create_access_token
from auth.tester_access import TesterAccess
from auth.tester_requests import TesterRequestService
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
    league_count: int = 0,
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
        leagueCount=league_count,
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

    def __init__(
        self,
        session: Session,
        settings: ApiSettings,
        impersonation_store: ImpersonationStore | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._impersonation_store = impersonation_store

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
        league_counts = dict(
            self._session.execute(
                select(LeagueMembership.user_id, func.count(LeagueMembership.id))
                .where(LeagueMembership.user_id.in_([user.id for user in rows]))
                .group_by(LeagueMembership.user_id)
            ).all()
        )
        return PaginatedAdminUsersResponse(
            items=[
                _to_user_response(
                    user, tester_emails, self._protected_emails(), league_counts.get(user.id, 0)
                )
                for user in rows
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

    # --- richieste di accesso dei non tester --------------------------------------------------
    def list_tester_requests(self, status: str | None) -> AdminTesterRequestListResponse:
        service = TesterRequestService(self._session)
        rows = service.list_requests(status)
        self._session.commit()  # la lettura ripulisce le richieste rifiutate scadute
        return AdminTesterRequestListResponse(
            requests=[self._tester_request_response(row) for row in rows]
        )

    def decide_tester_requests(
        self, *, actor: User, ids: list[UUID], action: str, note: str | None
    ) -> AdminTesterRequestListResponse:
        service = TesterRequestService(self._session)
        for request_id in ids:
            if action == "approve":
                entry = service.approve(request_id, actor_id=actor.id)
                self._audit_test_mode(actor, "tester_request_approved", {"id": str(entry.id)})
            else:
                entry = service.reject(request_id, actor_id=actor.id, note=note)
                self._audit_test_mode(actor, "tester_request_rejected", {"id": str(entry.id)})
        self._session.commit()
        return self.list_tester_requests(None)

    @staticmethod
    def _tester_request_response(row: TesterAccessRequest) -> AdminTesterRequestResponse:
        return AdminTesterRequestResponse(
            id=str(row.id),
            email=row.email,
            firstName=row.first_name,
            lastName=row.last_name,
            phone=row.phone,
            motivation=row.motivation,
            status=row.status,
            createdAt=row.created_at,
            decidedAt=row.decided_at,
            decisionNote=row.decision_note,
        )

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
        `impersonation_token_expire_minutes` (deliberately much shorter than a
        normal session's `jwt_access_token_expire_minutes`) and cannot be
        silently renewed. Its `jti` is also recorded in `ImpersonationStore`
        (Redis) so it can be cut off early with `revoke_impersonation`, instead
        of only ever expiring on its own. Operators can target other operators
        too (EP-operatore-test), except a protected one (`_is_protected`):
        without this, any operator — including one just promoted by another
        operator, with no extra check on who may promote — could mint a
        valid token for the protected account and fully take it over, which
        defeats the point of protecting it from demotion/deletion in the
        first place. Only impersonating yourself is blocked besides that.
        Every start is audited (`league_id=None`, same pattern as
        promote/revoke) — there is no "end" event since the token simply
        expires.
        """
        user = self._get_user_or_raise(target_user_id)
        if user.id == actor.id:
            raise CannotImpersonateSelfError()
        if self._is_protected(user):
            raise ProtectedOperatorError()

        jti = secrets.token_urlsafe(16)
        access_token, expires_in = create_access_token(
            user_id=user.id,
            secret=self._settings.resolved_jwt_secret(),
            expire_minutes=self._settings.impersonation_token_expire_minutes,
            impersonation_jti=jti,
        )
        if self._impersonation_store is not None:
            self._impersonation_store.start(jti=jti, target_user_id=user.id, ttl_seconds=expires_in)
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

    def revoke_impersonation(
        self, *, actor: User, target_user_id: UUID
    ) -> AdminImpersonationRevokeResponse:
        """Kill switch for `impersonate`: invalidates every impersonation access
        token currently active for `target_user_id`, immediately — not just the
        next one that would expire on its own. No-op (``revoked=0``) if none
        are active, or if Redis is unavailable (ImpersonationStore degrades
        open, same as elsewhere); the target's own session is never touched,
        only tokens carrying the ``imp`` claim.
        """
        user = self._get_user_or_raise(target_user_id)
        revoked = (
            self._impersonation_store.revoke_all_for_user(user.id)
            if self._impersonation_store is not None
            else 0
        )
        _logger.info(
            "admin user impersonation revoked",
            extra={
                "event": "admin_user_impersonation_revoked",
                "actor_id": str(actor.id),
                "target_user_id": str(user.id),
                "revoked_count": revoked,
            },
        )
        return AdminImpersonationRevokeResponse(revokedCount=revoked)

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
