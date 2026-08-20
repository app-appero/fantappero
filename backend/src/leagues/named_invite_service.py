"""Fantasy-coach directory and transactional named invitations."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Literal, NoReturn
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.rate_limit import AuthRateLimiter
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    LeagueMemberRole,
    NamedInviteStatus,
    UserType,
)
from fantasy_teams.factory import ensure_team_for_membership
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.named_league_invite import NamedLeagueInvite
from leagues.schemas import (
    CreateNamedLeagueInviteRequest,
    FantasyCoachDirectoryItem,
    FantasyCoachDirectoryResponse,
    NamedLeagueInviteResponse,
    RespondNamedLeagueInviteResponse,
)
from leagues.validators import validate_configurable_league_state
from observability.context import get_correlation_id
from observability.metrics import get_metrics


class NamedLeagueInviteService:
    def __init__(
        self,
        session: Session,
        rate_limiter: AuthRateLimiter | None = None,
    ) -> None:
        self._session = session
        self._rate_limiter = rate_limiter

    def directory(
        self,
        league_access: LeagueAccess,
        *,
        page: int,
        page_size: int,
        search: str | None,
        user_type: UserType | None,
        available: bool | None,
    ) -> FantasyCoachDirectoryResponse:
        self._check_rate_limit("coach_directory", league_access)
        now = datetime.now(UTC)
        self._expire_pending_for_league(league_access.league.id, now)
        latest_status = (
            select(NamedLeagueInvite.status)
            .where(
                NamedLeagueInvite.league_id == league_access.league.id,
                NamedLeagueInvite.recipient_id == User.id,
            )
            .order_by(NamedLeagueInvite.created_at.desc())
            .limit(1)
            .correlate(User)
            .scalar_subquery()
        )
        member_ids = select(LeagueMembership.user_id).where(
            LeagueMembership.league_id == league_access.league.id
        )
        effective_available = or_(
            User.user_type == UserType.AI,
            UserProfile.available_for_invites.is_(True),
        )
        conditions = [
            User.deleted_at.is_(None),
            User.email_verified_at.is_not(None),
            User.id != league_access.user.id,
            User.id.not_in(member_ids),
            UserProfile.display_name.is_not(None),
            UserProfile.display_name != "",
        ]
        if search:
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            if escaped:
                conditions.append(UserProfile.display_name.ilike(f"%{escaped}%", escape="\\"))
        if user_type is not None:
            conditions.append(User.user_type == user_type)
        if available is not None:
            conditions.append(effective_available if available else ~effective_available)

        base = (
            select(User, UserProfile, latest_status.label("invite_status"))
            .join(UserProfile, UserProfile.user_id == User.id)
            .where(*conditions)
        )
        total = (
            self._session.scalar(select(func.count()).select_from(base.order_by(None).subquery()))
            or 0
        )
        rows = self._session.execute(
            base.order_by(UserProfile.display_name.asc(), User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = [
            FantasyCoachDirectoryItem(
                userId=str(user.id),
                displayName=profile.display_name or "",
                avatarUrl=profile.avatar_url,
                userType=user.user_type.value,
                availableForInvites=(
                    user.user_type == UserType.AI or profile.available_for_invites
                ),
                namedInviteStatus=invite_status.value if invite_status is not None else None,
            )
            for user, profile, invite_status in rows
        ]
        get_metrics().incr("coach_directory_viewed_total", labels={"result": "success"})
        return FantasyCoachDirectoryResponse(
            items=items,
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=math.ceil(total / page_size) if total else 0,
        )

    def create(
        self,
        league_access: LeagueAccess,
        payload: CreateNamedLeagueInviteRequest,
    ) -> NamedLeagueInviteResponse:
        self._check_rate_limit("named_invite_create", league_access)
        league = self._lock_league(league_access.league.id)
        validate_configurable_league_state(league.state, subject="gli inviti nominativi")
        recipient = self._session.scalar(
            select(User)
            .where(User.id == payload.recipient_user_id, User.deleted_at.is_(None))
            .options(selectinload(User.profile))
        )
        if recipient is None or recipient.email_verified_at is None:
            self._fail("Fantallenatore non trovato.", "recipient_not_found", "not_found")
        if recipient.id == league_access.user.id:
            self._fail("Non puoi invitare te stesso.", "cannot_invite_self", "self")
        if self._membership(league.id, recipient.id) is not None:
            self._fail("Il fantallenatore è già nella lega.", "already_member", "already_member")
        if not self._is_available_for_invites(recipient):
            self._fail(
                "Il fantallenatore non è disponibile agli inviti.",
                "recipient_unavailable",
                "unavailable",
            )

        now = datetime.now(UTC)
        self._expire_pending(league.id, recipient.id, now)
        pending = self._session.scalar(
            select(NamedLeagueInvite).where(
                NamedLeagueInvite.league_id == league.id,
                NamedLeagueInvite.recipient_id == recipient.id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
            )
        )
        if pending is not None:
            self._fail("Invito già inviato.", "named_invite_already_pending", "duplicate")

        self._require_capacity(league, include_pending=True)
        invite = NamedLeagueInvite(
            league_id=league.id,
            recipient_id=recipient.id,
            created_by_id=league_access.user.id,
            status=(
                NamedInviteStatus.ACCEPTED
                if recipient.user_type == UserType.AI
                else NamedInviteStatus.PENDING
            ),
            expires_at=now + timedelta(days=payload.expires_in_days),
            responded_at=now if recipient.user_type == UserType.AI else None,
        )
        self._session.add(invite)
        self._session.flush()
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.NAMED_INVITE_CREATED,
            invite,
        )
        if recipient.user_type == UserType.AI:
            self._session.add(
                LeagueMembership(
                    league_id=league.id,
                    user_id=recipient.id,
                    role=LeagueMemberRole.MEMBER,
                )
            )
            self._add_audit(
                league.id,
                recipient.id,
                LeagueAuditAction.NAMED_INVITE_ACCEPTED,
                invite,
            )
        self._session.commit()
        get_metrics().incr(
            "named_invite_created_total",
            labels={"result": "auto_accepted" if recipient.user_type == UserType.AI else "success"},
        )
        return self._response(
            invite,
            league,
            recipient,
            auto_accepted=recipient.user_type == UserType.AI,
        )

    def received(self, user: User) -> list[NamedLeagueInviteResponse]:
        now = datetime.now(UTC)
        result = self._session.execute(
            update(NamedLeagueInvite)
            .where(
                NamedLeagueInvite.recipient_id == user.id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at <= now,
            )
            .values(status=NamedInviteStatus.EXPIRED)
        )
        if result.rowcount:
            self._session.commit()
        # Solo inviti ancora actionable: accettati/rifiutati/scaduti/revocati
        # non devono riapparire nella inbox dopo un refresh.
        invites = list(
            self._session.scalars(
                select(NamedLeagueInvite)
                .where(
                    NamedLeagueInvite.recipient_id == user.id,
                    NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                )
                .options(
                    selectinload(NamedLeagueInvite.league),
                    selectinload(NamedLeagueInvite.recipient).selectinload(User.profile),
                )
                .order_by(NamedLeagueInvite.created_at.desc())
            ).all()
        )
        return [self._response(row, row.league, row.recipient) for row in invites]

    def accept(self, user: User, invite_id: UUID) -> RespondNamedLeagueInviteResponse:
        return self._respond(user, invite_id, action="accept")

    def decline(self, user: User, invite_id: UUID) -> RespondNamedLeagueInviteResponse:
        return self._respond(user, invite_id, action="decline")

    def revoke(
        self,
        league_access: LeagueAccess,
        invite_id: UUID,
    ) -> NamedLeagueInviteResponse:
        league = self._lock_league(league_access.league.id)
        invite = self._load_invite(invite_id, for_update=True)
        if invite is None or invite.league_id != league.id:
            self._fail("Invito non trovato.", "named_invite_not_found", "not_found")
        if invite.status == NamedInviteStatus.REVOKED:
            return self._response(invite, league, invite.recipient)
        if invite.status != NamedInviteStatus.PENDING:
            self._fail("L'invito non è più revocabile.", "named_invite_not_pending", "not_pending")
        now = datetime.now(UTC)
        invite.status = NamedInviteStatus.REVOKED
        invite.revoked_at = now
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.NAMED_INVITE_REVOKED,
            invite,
        )
        self._session.commit()
        get_metrics().incr("named_invite_revoked_total", labels={"result": "success"})
        return self._response(invite, league, invite.recipient)

    def _respond(
        self,
        user: User,
        invite_id: UUID,
        *,
        action: Literal["accept", "decline"],
    ) -> RespondNamedLeagueInviteResponse:
        invite = self._load_invite(invite_id, for_update=False)
        if invite is None or invite.recipient_id != user.id:
            self._fail("Invito non trovato.", "named_invite_not_found", "not_found")
        desired = NamedInviteStatus.ACCEPTED if action == "accept" else NamedInviteStatus.DECLINED
        if invite.status == desired:
            return RespondNamedLeagueInviteResponse(
                **self._response(invite, invite.league, invite.recipient).model_dump(),
                alreadyProcessed=True,
            )
        if invite.status != NamedInviteStatus.PENDING:
            self._fail(
                "L'invito è già stato elaborato.",
                "named_invite_already_processed",
                "already_processed",
            )

        league = self._lock_league(invite.league_id)
        invite = self._load_invite(invite_id, for_update=True)
        if invite is None or invite.recipient_id != user.id:
            self._fail("Invito non trovato.", "named_invite_not_found", "not_found")
        if invite.status == desired:
            return RespondNamedLeagueInviteResponse(
                **self._response(invite, league, invite.recipient).model_dump(),
                alreadyProcessed=True,
            )
        if invite.status != NamedInviteStatus.PENDING:
            self._fail(
                "L'invito è già stato elaborato.",
                "named_invite_already_processed",
                "already_processed",
            )
        now = datetime.now(UTC)
        if invite.expires_at <= now:
            invite.status = NamedInviteStatus.EXPIRED
            self._session.commit()
            self._fail("L'invito è scaduto.", "named_invite_expired", "expired")
        validate_configurable_league_state(league.state, subject="gli ingressi nella lega")

        if action == "accept":
            recipient = invite.recipient
            if recipient.deleted_at is not None or recipient.email_verified_at is None:
                self._fail("Fantallenatore non trovato.", "recipient_not_found", "not_found")
            if not self._is_available_for_invites(recipient):
                self._fail(
                    "Il fantallenatore non è disponibile agli inviti.",
                    "recipient_unavailable",
                    "unavailable",
                )
            existing = self._membership(league.id, user.id)
            if existing is None:
                self._require_capacity(league, include_pending=False)
                membership = LeagueMembership(
                    league_id=league.id,
                    user_id=user.id,
                    role=LeagueMemberRole.MEMBER,
                )
                self._session.add(membership)
                self._session.flush()
                team, created = ensure_team_for_membership(
                    self._session,
                    membership,
                    name=user.display_name,
                    actor_id=user.id,
                )
                if created:
                    self._session.add(
                        LeagueAuditEvent(
                            league_id=league.id,
                            actor_id=user.id,
                            action=LeagueAuditAction.FANTASY_TEAM_CREATED,
                            correlation_id=get_correlation_id(),
                            details={
                                "fantasyTeamId": str(team.id),
                                "membershipId": str(membership.id),
                            },
                        )
                    )
            audit_action = LeagueAuditAction.NAMED_INVITE_ACCEPTED
        else:
            audit_action = LeagueAuditAction.NAMED_INVITE_DECLINED
        invite.status = desired
        invite.responded_at = now
        self._add_audit(league.id, user.id, audit_action, invite)
        self._session.commit()
        get_metrics().incr(
            f"named_invite_{'accepted' if action == 'accept' else 'declined'}_total",
            labels={"result": "success"},
        )
        return RespondNamedLeagueInviteResponse(
            **self._response(invite, league, invite.recipient).model_dump(),
            alreadyProcessed=False,
        )

    def _require_capacity(self, league: League, *, include_pending: bool) -> None:
        if league.rules is None:
            self._fail(
                "Regolamento lega non configurato.",
                "league_rules_not_found",
                "rules_missing",
            )
        members = (
            self._session.scalar(
                select(func.count(LeagueMembership.id)).where(
                    LeagueMembership.league_id == league.id
                )
            )
            or 0
        )
        pending = 0
        if include_pending:
            pending = (
                self._session.scalar(
                    select(func.count(NamedLeagueInvite.id)).where(
                        NamedLeagueInvite.league_id == league.id,
                        NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                        NamedLeagueInvite.expires_at > datetime.now(UTC),
                    )
                )
                or 0
            )
        if members + pending >= league.rules.participant_count:
            self._fail("La lega non ha posti disponibili.", "league_full", "full")

    def _load_invite(
        self,
        invite_id: UUID,
        *,
        for_update: bool,
    ) -> NamedLeagueInvite | None:
        statement = (
            select(NamedLeagueInvite)
            .where(NamedLeagueInvite.id == invite_id)
            .options(
                selectinload(NamedLeagueInvite.league).selectinload(League.rules),
                selectinload(NamedLeagueInvite.recipient).selectinload(User.profile),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalar(
            select(League)
            .where(League.id == league_id)
            .options(selectinload(League.rules))
            .with_for_update()
        )
        if league is None:
            self._fail("Lega non trovata.", "league_not_found", "not_found")
        return league

    def _membership(self, league_id: UUID, user_id: UUID) -> LeagueMembership | None:
        return self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.user_id == user_id,
            )
        )

    def _expire_pending(self, league_id: UUID, recipient_id: UUID, now: datetime) -> None:
        rows = self._session.scalars(
            select(NamedLeagueInvite).where(
                NamedLeagueInvite.league_id == league_id,
                NamedLeagueInvite.recipient_id == recipient_id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at <= now,
            )
        ).all()
        for row in rows:
            row.status = NamedInviteStatus.EXPIRED
        if rows:
            self._session.flush()

    def _expire_pending_for_league(self, league_id: UUID, now: datetime) -> None:
        result = self._session.execute(
            update(NamedLeagueInvite)
            .where(
                NamedLeagueInvite.league_id == league_id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at <= now,
            )
            .values(status=NamedInviteStatus.EXPIRED)
        )
        if result.rowcount:
            self._session.flush()

    @staticmethod
    def _is_available_for_invites(user: User) -> bool:
        if user.user_type == UserType.AI:
            return True
        return user.profile is not None and user.profile.available_for_invites

    def _check_rate_limit(self, endpoint: str, access: LeagueAccess) -> None:
        if self._rate_limiter is not None:
            self._rate_limiter.check(
                endpoint=endpoint,
                key=f"{access.user.id}:{access.league.id}",
                limit=120 if endpoint == "coach_directory" else 30,
                window_seconds=60,
            )

    def _add_audit(
        self,
        league_id: UUID,
        actor_id: UUID,
        action: LeagueAuditAction,
        invite: NamedLeagueInvite,
    ) -> None:
        self._session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=actor_id,
                action=action,
                correlation_id=get_correlation_id(),
                details={
                    "namedInviteId": str(invite.id),
                    "recipientUserId": str(invite.recipient_id),
                },
            )
        )

    @staticmethod
    def _response(
        invite: NamedLeagueInvite,
        league: League,
        recipient: User,
        *,
        auto_accepted: bool = False,
    ) -> NamedLeagueInviteResponse:
        display_name = (
            recipient.profile.display_name
            if recipient.profile is not None and recipient.profile.display_name
            else "Fantallenatore"
        )
        return NamedLeagueInviteResponse(
            id=str(invite.id),
            leagueId=str(invite.league_id),
            leagueName=league.name,
            recipientUserId=str(recipient.id),
            recipientDisplayName=display_name,
            recipientUserType=recipient.user_type.value,
            status=invite.status.value,
            expiresAt=invite.expires_at,
            respondedAt=invite.responded_at,
            createdAt=invite.created_at,
            autoAccepted=auto_accepted,
        )

    @staticmethod
    def _fail(message: str, code: str, result: str) -> NoReturn:
        get_metrics().incr("named_invite_operation_total", labels={"result": result})
        raise ValidationAuthError(message, code=code)
