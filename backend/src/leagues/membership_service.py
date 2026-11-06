"""Atomic league participant management (EP03-04)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from auth.blocklist import BlockList
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    LeagueCalendarStatus,
    LeagueMemberRole,
    NamedInviteStatus,
    UserType,
    league_member_role_to_league_role,
)
from fantasy_teams.models import FantasyTeam
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.models.named_league_invite import NamedLeagueInvite
from leagues.schemas import LeagueMemberResponse
from leagues.validators import (
    MIN_PARTICIPANTS,
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

    def list(
        self,
        league_access: LeagueAccess,
        *,
        include_email: bool = False,
    ) -> list[LeagueMemberResponse]:
        memberships = self._load_memberships(league_access.league.id)
        return [
            self._to_response(membership, include_email=include_email) for membership in memberships
        ]

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

        response = self._to_response(membership, include_email=True)
        self._session.delete(membership)
        self._session.flush()
        self._release_accepted_named_invites(league.id, target_user_id)

        remaining = (
            self._session.scalar(
                select(func.count(LeagueMembership.id)).where(
                    LeagueMembership.league_id == league.id
                )
            )
            or 0
        )
        self._sync_participant_count_after_removal(
            league,
            actor_id=league_access.user.id,
            remaining=remaining,
        )
        self._invalidate_stale_draft_calendar(league.id)

        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.LEAGUE_MEMBER_REMOVED,
        )
        self._session.commit()
        get_metrics().incr("league_member_removed_total", labels={"result": "success"})
        logger.info("league_member_removed", extra={"result": "success"})
        return response

    def replace(
        self,
        league_access: LeagueAccess,
        target_user_id: UUID,
        new_user_id: UUID,
    ) -> LeagueMemberResponse:
        """Sostituisce un fantallenatore con un altro, mantenendo squadra, rosa, formazioni e punti.

        Serve, ad esempio, quando l'account di un partecipante è stato eliminato: chi subentra
        eredita la squadra così com'è. Vale in qualsiasi fase della lega.
        """
        metric = "league_member_replaced_total"
        league = self._lock_league(league_access.league.id)
        membership = self._get_membership(league.id, target_user_id)
        if membership is None:
            self._fail(
                "Partecipante non trovato.",
                code="member_not_found",
                metric=metric,
                result="not_found",
            )
        if membership.role == LeagueMemberRole.OWNER:
            self._fail(
                "Per sostituire l'amministratore trasferisci prima il ruolo di amministratore.",
                code="cannot_replace_admin",
                metric=metric,
                result="cannot_replace_admin",
            )
        if new_user_id == target_user_id:
            self._fail(
                "Scegli un fantallenatore diverso da quello da sostituire.",
                code="same_coach",
                metric=metric,
                result="same_coach",
            )
        new_user = self._session.scalars(
            select(User)
            .where(User.id == new_user_id, User.deleted_at.is_(None))
            .options(selectinload(User.profile))
        ).first()
        if new_user is None:
            self._fail(
                "Fantallenatore non trovato.",
                code="coach_not_found",
                metric=metric,
                result="coach_not_found",
            )
        already = self._session.scalar(
            select(LeagueMembership.id).where(
                LeagueMembership.league_id == league.id,
                LeagueMembership.user_id == new_user_id,
            )
        )
        if already is not None:
            self._fail(
                "Questo fantallenatore è già in lega.",
                code="already_member",
                metric=metric,
                result="already_member",
            )
        available = new_user.user_type == UserType.AI or bool(
            new_user.profile is not None and new_user.profile.available_for_invites
        )
        if not available or BlockList(self._session).is_blocked(new_user.email):
            self._fail(
                "Questo fantallenatore non è disponibile.",
                code="coach_not_available",
                metric=metric,
                result="coach_not_available",
            )

        old_name = membership.user.display_name
        membership.user_id = new_user.id
        membership.historical_display_name = None
        self._session.flush()
        self._session.refresh(membership)
        # La squadra segue la membership (rosa, formazioni, punti); il nome mostrato è quello nuovo.
        team = self._session.scalars(
            select(FantasyTeam).where(FantasyTeam.membership_id == membership.id)
        ).first()
        if team is not None:
            team.name = new_user.display_name
        self._release_accepted_named_invites(league.id, target_user_id)
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_MEMBER_JOINED,
                correlation_id=get_correlation_id(),
                details={
                    "source": "coach_replaced",
                    "replacedUserId": str(target_user_id),
                    "replacedDisplayName": old_name,
                    "newUserId": str(new_user.id),
                },
            )
        )
        self._session.commit()
        get_metrics().incr(metric, labels={"result": "success"})
        logger.info("league_member_replaced", extra={"result": "success"})
        return self._to_response(membership, include_email=True)

    def transfer_admin(
        self,
        league_access: LeagueAccess,
        target_user_id: UUID,
        *,
        keep_current: bool = False,
    ) -> LeagueMemberResponse:
        """Passa il ruolo di amministratore a un altro partecipante, in qualsiasi fase della lega.

        Con ``keep_current`` chi lo fa resta amministratore: la lega ha due (o più) amministratori
        con gli stessi poteri («co-amministratore»). Senza, il ruolo passa e chi lo fa torna
        partecipante.
        """
        metric = "league_admin_transferred_total"
        league = self._lock_league(league_access.league.id)
        memberships = self._load_memberships(league.id, for_update=True)
        actor = next(
            (row for row in memberships if row.user_id == league_access.user.id),
            None,
        )
        target = next((row for row in memberships if row.user_id == target_user_id), None)
        if target is None:
            self._fail(
                "Partecipante non trovato.",
                code="member_not_found",
                metric=metric,
                result="not_found",
            )
        if actor is None or actor.role != LeagueMemberRole.OWNER:
            self._fail(
                "La lega deve avere un amministratore.",
                code="league_admin_required",
                metric=metric,
                result="admin_missing",
            )
        if target.role == LeagueMemberRole.OWNER:
            # Già amministratore (anche se è chi sta facendo la richiesta): nessuna modifica.
            get_metrics().incr(metric, labels={"result": "noop"})
            return self._to_response(target, include_email=True)

        try:
            validate_admin_transfer_target(target.role)
        except ValidationAuthError:
            get_metrics().incr(metric, labels={"result": "invalid_target"})
            raise

        target.role = LeagueMemberRole.OWNER
        if not keep_current:
            actor.role = LeagueMemberRole.MEMBER
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_ADMIN_TRANSFERRED,
                correlation_id=get_correlation_id(),
                details={
                    "mode": "co_admin" if keep_current else "transfer",
                    "targetUserId": str(target_user_id),
                },
            )
        )
        self._session.commit()
        get_metrics().incr(metric, labels={"result": "success"})
        logger.info("league_admin_transferred", extra={"result": "success"})
        return self._to_response(target, include_email=True)

    def revoke_admin(
        self,
        league_access: LeagueAccess,
        target_user_id: UUID,
    ) -> LeagueMemberResponse:
        """Toglie il ruolo di amministratore a un co-amministratore (ne resta almeno uno)."""
        metric = "league_admin_revoked_total"
        league = self._lock_league(league_access.league.id)
        memberships = self._load_memberships(league.id, for_update=True)
        target = next((row for row in memberships if row.user_id == target_user_id), None)
        if target is None:
            self._fail(
                "Partecipante non trovato.",
                code="member_not_found",
                metric=metric,
                result="not_found",
            )
        if target.role != LeagueMemberRole.OWNER:
            get_metrics().incr(metric, labels={"result": "noop"})
            return self._to_response(target, include_email=True)
        admins = [row for row in memberships if row.role == LeagueMemberRole.OWNER]
        if len(admins) <= 1:
            self._fail(
                "La lega deve avere almeno un amministratore.",
                code="last_league_admin",
                metric=metric,
                result="last_admin",
            )
        target.role = LeagueMemberRole.MEMBER
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_ADMIN_TRANSFERRED,
                correlation_id=get_correlation_id(),
                details={"mode": "revoke", "targetUserId": str(target_user_id)},
            )
        )
        self._session.commit()
        get_metrics().incr(metric, labels={"result": "success"})
        logger.info("league_admin_revoked", extra={"result": "success"})
        return self._to_response(target, include_email=True)

    def _sync_participant_count_after_removal(
        self,
        league: League,
        *,
        actor_id: UUID,
        remaining: int,
    ) -> None:
        """Abbassa il target regolamento agli iscritti rimasti (min 4).

        Se restano meno di 4 iscritti non forziamo un valore fuori range: il
        mismatch resta e blocca asta/calendario finché non si torna nel range.
        """
        if remaining < MIN_PARTICIPANTS:
            return
        rules = self._session.scalars(
            select(LeagueRules).where(LeagueRules.league_id == league.id).with_for_update()
        ).first()
        if rules is None or rules.participant_count <= remaining:
            return
        previous = rules.participant_count
        rules.participant_count = remaining
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=actor_id,
                action=LeagueAuditAction.LEAGUE_RULES_UPDATED,
                correlation_id=get_correlation_id(),
                details={
                    "source": "member_removed",
                    "participantCount": {"from": previous, "to": remaining},
                },
            )
        )

    def _release_accepted_named_invites(self, league_id: UUID, user_id: UUID) -> None:
        """Un accepted rimasto dopo l'uscita teneva il fantallenatore su «Aggiunto».

        Il vincolo di tabella vuole `responded_at` solo per accepted/declined e
        `revoked_at` solo per revoked: la riga torna revocata e la directory
        può proporre di nuovo «Invita».
        """
        now = datetime.now(UTC)
        invites = self._session.scalars(
            select(NamedLeagueInvite).where(
                NamedLeagueInvite.league_id == league_id,
                NamedLeagueInvite.recipient_id == user_id,
                NamedLeagueInvite.status == NamedInviteStatus.ACCEPTED,
            )
        ).all()
        for invite in invites:
            invite.status = NamedInviteStatus.REVOKED
            invite.responded_at = None
            invite.revoked_at = now

    def _invalidate_stale_draft_calendar(self, league_id: UUID) -> None:
        """Cancella l'anteprima H2H: i partecipanti sono cambiati, va rigenerata."""
        calendar = self._session.scalars(
            select(LeagueCalendar)
            .where(
                LeagueCalendar.league_id == league_id,
                LeagueCalendar.status == LeagueCalendarStatus.DRAFT,
            )
            .with_for_update()
        ).first()
        if calendar is None:
            return
        self._session.delete(calendar)

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
    def _to_response(
        membership: LeagueMembership,
        *,
        include_email: bool = False,
    ) -> LeagueMemberResponse:
        return LeagueMemberResponse(
            userId=str(membership.user_id),
            displayName=membership.user.display_name,
            avatarUrl=membership.user.avatar_url,
            userType=membership.user.user_type.value,
            role=league_member_role_to_league_role(membership.role).value,
            joinedAt=membership.created_at,
            email=membership.user.email if include_email else None,
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
