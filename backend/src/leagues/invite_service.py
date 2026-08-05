"""Domain service for league invitations and atomic membership entry."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal, NoReturn
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from auth.security import generate_opaque_token, hash_opaque_token
from authorization.context import LeagueAccess
from config.settings.api import ApiSettings
from database.enums import (
    LeagueAuditAction,
    LeagueMemberRole,
    LeagueState,
    NamedInviteStatus,
)
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_invite import LeagueInvite
from leagues.models.league_membership import LeagueMembership
from leagues.models.named_league_invite import NamedLeagueInvite
from leagues.schemas import (
    AcceptLeagueInviteRequest,
    AcceptLeagueInviteResponse,
    CreateLeagueInviteRequest,
    CreateLeagueInviteResponse,
    LeagueInviteResponse,
)
from leagues.validators import (
    validate_configurable_league_state,
    validate_invite_credential,
    validate_invite_expiry_days,
)
from observability.context import get_correlation_id
from observability.metrics import get_metrics

_INVITE_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_INVITE_CODE_LENGTH = 10


class LeagueInviteService:
    def __init__(self, session: Session, settings: ApiSettings) -> None:
        self._session = session
        self._settings = settings

    def create(
        self,
        league_access: LeagueAccess,
        payload: CreateLeagueInviteRequest,
    ) -> CreateLeagueInviteResponse:
        expires_in_days = validate_invite_expiry_days(payload.expires_in_days)
        league = self._lock_league(league_access.league.id)
        rules = league.rules
        self._require_configurable(
            league.state,
            subject="gli inviti",
            metric="league_invite_created_total",
        )
        if rules is None or not rules.allow_manual_invites:
            self._fail_create(
                "Gli inviti manuali non sono abilitati per questa lega.",
                code="manual_invites_disabled",
                result="disabled",
            )

        token = generate_opaque_token()
        raw_code = "".join(
            secrets.choice(_INVITE_CODE_ALPHABET) for _ in range(_INVITE_CODE_LENGTH)
        )
        now = datetime.now(UTC)
        invite = LeagueInvite(
            league_id=league.id,
            created_by_id=league_access.user.id,
            token_hash=hash_opaque_token(token),
            code_hash=hash_opaque_token(raw_code),
            expires_at=now + timedelta(days=expires_in_days),
        )
        self._session.add(invite)
        self._session.flush()
        self._add_audit(league.id, league_access.user.id, LeagueAuditAction.LEAGUE_INVITE_CREATED)
        self._session.commit()
        get_metrics().incr("league_invite_created_total", labels={"result": "success"})

        formatted_code = f"{raw_code[:5]}-{raw_code[5:]}"
        invite_url = (
            f"{self._settings.web_app_base_url.rstrip('/')}/leghe/invito"
            f"?token={quote(token, safe='')}"
        )
        return CreateLeagueInviteResponse(
            **self._response_values(invite),
            token=token,
            code=formatted_code,
            inviteUrl=invite_url,
        )

    def list(self, league_access: LeagueAccess) -> list[LeagueInviteResponse]:
        invites = self._session.scalars(
            select(LeagueInvite)
            .where(LeagueInvite.league_id == league_access.league.id)
            .order_by(LeagueInvite.created_at.desc())
        ).all()
        return [LeagueInviteResponse(**self._response_values(invite)) for invite in invites]

    def revoke(self, league_access: LeagueAccess, invite_id: UUID) -> LeagueInviteResponse:
        league = self._lock_league(league_access.league.id)
        self._require_configurable(
            league.state,
            subject="gli inviti",
            metric="league_invite_revoked_total",
        )
        invite = self._session.scalars(
            select(LeagueInvite).where(
                LeagueInvite.id == invite_id,
                LeagueInvite.league_id == league_access.league.id,
            )
        ).first()
        if invite is None:
            get_metrics().incr("league_invite_revoked_total", labels={"result": "not_found"})
            raise ValidationAuthError("Invito non trovato.", code="invite_not_found")
        if invite.revoked_at is not None:
            get_metrics().incr("league_invite_revoked_total", labels={"result": "noop"})
            return LeagueInviteResponse(**self._response_values(invite))

        invite.revoked_at = datetime.now(UTC)
        self._add_audit(
            invite.league_id,
            league_access.user.id,
            LeagueAuditAction.LEAGUE_INVITE_REVOKED,
        )
        self._session.commit()
        get_metrics().incr("league_invite_revoked_total", labels={"result": "success"})
        return LeagueInviteResponse(**self._response_values(invite))

    def accept(
        self,
        user: User,
        payload: AcceptLeagueInviteRequest,
    ) -> AcceptLeagueInviteResponse:
        try:
            credential_type, credential = validate_invite_credential(
                token=payload.token,
                code=payload.code,
            )
        except ValidationAuthError:
            get_metrics().incr("league_invite_accepted_total", labels={"result": "invalid"})
            raise

        credential_hash = hash_opaque_token(credential)
        condition = (
            LeagueInvite.token_hash == credential_hash
            if credential_type == "token"
            else LeagueInvite.code_hash == credential_hash
        )
        invite = self._session.scalars(select(LeagueInvite).where(condition)).first()
        if invite is None:
            self._fail_accept("L'invito non è valido.", code="invalid_invite", result="invalid")

        league = self._lock_league(invite.league_id)
        self._session.refresh(invite)
        now = datetime.now(UTC)
        if invite.revoked_at is not None:
            self._fail_accept(
                "L'invito è stato revocato.",
                code="invite_revoked",
                result="revoked",
            )
        if invite.expires_at <= now:
            self._fail_accept(
                "L'invito è scaduto.",
                code="invite_expired",
                result="expired",
            )
        self._require_configurable(
            league.state,
            subject="gli ingressi nella lega",
            metric="league_invite_accepted_total",
        )

        existing = self._session.scalars(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league.id,
                LeagueMembership.user_id == user.id,
            )
        ).first()
        if existing is not None:
            get_metrics().incr(
                "league_invite_accepted_total",
                labels={"result": "already_member"},
            )
            return AcceptLeagueInviteResponse(
                leagueId=str(league.id),
                leagueName=league.name,
                alreadyMember=True,
            )

        rules = league.rules
        if rules is None:
            self._fail_accept(
                "Regolamento lega non configurato.",
                code="league_rules_not_found",
                result="rules_missing",
            )
        member_count = self._session.scalar(
            select(func.count(LeagueMembership.id)).where(LeagueMembership.league_id == league.id)
        )
        pending_named_count = (
            self._session.scalar(
                select(func.count(NamedLeagueInvite.id)).where(
                    NamedLeagueInvite.league_id == league.id,
                    NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                    NamedLeagueInvite.expires_at > now,
                )
            )
            or 0
        )
        own_named_invite = self._session.scalar(
            select(NamedLeagueInvite)
            .where(
                NamedLeagueInvite.league_id == league.id,
                NamedLeagueInvite.recipient_id == user.id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at > now,
            )
            .with_for_update()
        )
        projected_occupancy = (
            (member_count or 0) + pending_named_count + (0 if own_named_invite is not None else 1)
        )
        if projected_occupancy > rules.participant_count:
            self._fail_accept(
                "La lega ha raggiunto il numero massimo di partecipanti.",
                code="league_full",
                result="full",
            )

        self._session.add(
            LeagueMembership(
                league_id=league.id,
                user_id=user.id,
                role=LeagueMemberRole.MEMBER,
            )
        )
        if own_named_invite is not None:
            own_named_invite.status = NamedInviteStatus.ACCEPTED
            own_named_invite.responded_at = now
            self._add_audit(
                league.id,
                user.id,
                LeagueAuditAction.NAMED_INVITE_ACCEPTED,
            )
        self._add_audit(league.id, user.id, LeagueAuditAction.LEAGUE_MEMBER_JOINED)
        self._session.commit()
        get_metrics().incr("league_invite_accepted_total", labels={"result": "success"})
        return AcceptLeagueInviteResponse(
            leagueId=str(league.id),
            leagueName=league.name,
            alreadyMember=False,
        )

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League)
            .where(League.id == league_id)
            .options(selectinload(League.rules))
            .with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

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
    def _require_configurable(state: LeagueState, *, subject: str, metric: str) -> None:
        try:
            validate_configurable_league_state(state, subject=subject)
        except ValidationAuthError:
            get_metrics().incr(metric, labels={"result": "league_not_draft"})
            raise

    @staticmethod
    def _status(invite: LeagueInvite) -> Literal["active", "expired", "revoked"]:
        if invite.revoked_at is not None:
            return "revoked"
        if invite.expires_at <= datetime.now(UTC):
            return "expired"
        return "active"

    def _response_values(self, invite: LeagueInvite) -> dict[str, object]:
        return {
            "id": str(invite.id),
            "leagueId": str(invite.league_id),
            "status": self._status(invite),
            "expiresAt": invite.expires_at,
            "revokedAt": invite.revoked_at,
            "createdAt": invite.created_at,
        }

    @staticmethod
    def _fail_create(message: str, *, code: str, result: str) -> NoReturn:
        get_metrics().incr("league_invite_created_total", labels={"result": result})
        raise ValidationAuthError(message, code=code)

    @staticmethod
    def _fail_accept(message: str, *, code: str, result: str) -> NoReturn:
        get_metrics().incr("league_invite_accepted_total", labels={"result": result})
        raise ValidationAuthError(message, code=code)
