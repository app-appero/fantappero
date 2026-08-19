"""Trade proposal service: create, list and cancel (EP08-05 / FR-MKT-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import LeagueAuditAction, NotificationCategory, TradeStatus
from fantasy_teams.factory import (
    ensure_team_for_membership,
    find_team_by_id,
    find_team_for_membership,
)
from fantasy_teams.ledger import find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from market.models import TradeProposal
from market.trade_execution import execute_trade
from market.trade_schemas import (
    CounterTradeProposalRequest,
    CreateTradeProposalRequest,
    TradeAthleteResponse,
    TradeProposalListResponse,
    TradeProposalResponse,
)
from market.trade_validators import (
    parse_athlete_ids,
    validate_active_proposal_limit,
    validate_athletes_owned_by_team,
    validate_distinct_teams,
    validate_no_athlete_overlap,
    validate_offered_credits_within_balance,
    validate_trade_expiry,
    validate_trade_sides_not_empty,
    validate_trades_enabled,
)
from market.windows import effective_trade_status
from notifications.recipients import user_ids_for_teams
from notifications.service import NotificationService
from observability.metrics import get_metrics
from sports_data.roster.models import Athlete


def _parse_required_datetime(value: str, *, field: str) -> datetime:
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationAuthError(
            f"Il campo {field} non è una data ISO-8601 valida.",
            code="invalid_datetime",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class TradeService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_proposal(
        self,
        league_access: LeagueAccess,
        payload: CreateTradeProposalRequest,
    ) -> TradeProposalResponse:
        league_id = league_access.league.id
        proposer = self._my_team(league_access)
        try:
            recipient_team_id = UUID(payload.recipient_team_id)
        except ValueError as exc:
            raise ValidationAuthError(
                "Identificativo squadra destinataria non valido.",
                code="invalid_recipient_team_id",
            ) from exc
        recipient = find_team_by_id(self._session, league_id=league_id, team_id=recipient_team_id)
        if recipient is None:
            raise ValidationAuthError(
                "Squadra destinataria non trovata in questa lega.",
                code="recipient_team_not_found",
            )

        proposal = self._build_validated_proposal(
            league_id=league_id,
            proposer=proposer,
            recipient=recipient,
            offered_athlete_ids_raw=payload.offered_athlete_ids,
            requested_athlete_ids_raw=payload.requested_athlete_ids,
            offered_credits=payload.offered_credits,
            requested_credits=payload.requested_credits,
            expires_at_raw=payload.expires_at,
            created_by=league_access.user.id,
        )
        self._session.add(proposal)
        self._session.flush()
        self._add_audit(
            league_id,
            league_access.user.id,
            LeagueAuditAction.MARKET_TRADE_PROPOSED,
            details={
                "proposalId": str(proposal.id),
                "proposerTeamId": str(proposer.id),
                "recipientTeamId": str(recipient.id),
                "offeredAthleteIds": proposal.offered_athlete_ids,
                "requestedAthleteIds": proposal.requested_athlete_ids,
                "offeredCredits": proposal.offered_credits,
                "requestedCredits": proposal.requested_credits,
                "expiresAt": proposal.expires_at.isoformat(),
            },
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_created_total")
        return self._to_response(proposal)

    def _build_validated_proposal(
        self,
        *,
        league_id: UUID,
        proposer: FantasyTeam,
        recipient: FantasyTeam,
        offered_athlete_ids_raw: list[str],
        requested_athlete_ids_raw: list[str],
        offered_credits: int,
        requested_credits: int,
        expires_at_raw: str,
        created_by: UUID,
    ) -> TradeProposal:
        rules = self._session.scalar(select(LeagueRules).where(LeagueRules.league_id == league_id))
        validate_trades_enabled(allow_trades=rules.allow_trades if rules else True)
        validate_distinct_teams(proposer_team_id=proposer.id, recipient_team_id=recipient.id)

        offered_athlete_ids = parse_athlete_ids(offered_athlete_ids_raw, field="offerta")
        requested_athlete_ids = parse_athlete_ids(requested_athlete_ids_raw, field="richiesta")
        validate_no_athlete_overlap(
            offered_athlete_ids=offered_athlete_ids,
            requested_athlete_ids=requested_athlete_ids,
        )
        validate_trade_sides_not_empty(
            offered_athlete_ids=offered_athlete_ids,
            offered_credits=offered_credits,
            requested_athlete_ids=requested_athlete_ids,
            requested_credits=requested_credits,
        )
        validate_athletes_owned_by_team(
            athlete_ids=offered_athlete_ids,
            owned_athlete_ids=self._roster_athlete_ids(proposer.id),
            team_label="della tua squadra",
        )
        validate_athletes_owned_by_team(
            athlete_ids=requested_athlete_ids,
            owned_athlete_ids=self._roster_athlete_ids(recipient.id),
            team_label="della squadra destinataria",
        )

        limit = rules.max_active_trade_proposals_per_team if rules else 10
        validate_active_proposal_limit(
            active_count=self._count_active_proposals(proposer.id), limit=limit
        )

        account = find_account_for_team(self._session, proposer.id)
        balance = account.balance if account is not None else 0
        validate_offered_credits_within_balance(offered_credits=offered_credits, balance=balance)

        now = datetime.now(UTC)
        expires_at = _parse_required_datetime(expires_at_raw, field="expiresAt")
        validate_trade_expiry(expires_at, now=now)

        return TradeProposal(
            league_id=league_id,
            proposer_team_id=proposer.id,
            recipient_team_id=recipient.id,
            offered_athlete_ids=[str(value) for value in offered_athlete_ids],
            requested_athlete_ids=[str(value) for value in requested_athlete_ids],
            offered_credits=offered_credits,
            requested_credits=requested_credits,
            expires_at=expires_at,
            created_by=created_by,
        )

    def cancel_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
    ) -> TradeProposalResponse:
        team = self._my_team(league_access)
        proposal = self._session.scalars(
            select(TradeProposal).where(TradeProposal.id == proposal_id).with_for_update()
        ).first()
        if proposal is None or proposal.league_id != league_access.league.id:
            raise ValidationAuthError("Proposta non trovata.", code="trade_proposal_not_found")
        if proposal.proposer_team_id != team.id:
            raise ValidationAuthError(
                "Solo chi ha proposto lo scambio può annullarlo.",
                code="trade_cancel_forbidden",
            )
        now = datetime.now(UTC)
        if effective_trade_status(proposal, now=now) != TradeStatus.PROPOSED:
            raise ValidationAuthError(
                "La proposta non è più annullabile.",
                code="trade_not_cancellable",
            )
        proposal.status = TradeStatus.CANCELLED
        self._session.flush()
        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_TRADE_CANCELLED,
            details={"proposalId": str(proposal.id)},
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_cancelled_total")
        return self._to_response(proposal)

    def reject_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
    ) -> TradeProposalResponse:
        team = self._my_team(league_access)
        proposal = self._lock_actionable_proposal_as_recipient(proposal_id, league_access, team)
        proposal.status = TradeStatus.REJECTED
        proposal.decided_at = datetime.now(UTC)
        self._session.flush()
        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_TRADE_REJECTED,
            details={"proposalId": str(proposal.id)},
        )
        self._notify_trade_status(
            proposal_id=proposal.id,
            status=TradeStatus.REJECTED,
            team_ids=[proposal.proposer_team_id],
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_rejected_total")
        return self._to_response(proposal)

    def accept_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
    ) -> TradeProposalResponse:
        team = self._my_team(league_access)
        proposal = self._lock_actionable_proposal_as_recipient(proposal_id, league_access, team)
        league = self._session.get(League, league_access.league.id)
        assert league is not None
        proposer_team = self._session.get(FantasyTeam, proposal.proposer_team_id)
        recipient_team = self._session.get(FantasyTeam, proposal.recipient_team_id)
        assert proposer_team is not None and recipient_team is not None

        rules = self._session.scalar(
            select(LeagueRules).where(LeagueRules.league_id == league_access.league.id)
        )
        if rules is not None and rules.require_trade_approval:
            # Deferred to admin approval (EP08-07): nothing is moved yet, so no
            # re-validation is needed here — execute_trade re-validates everything
            # fresh at approval time, when the assets actually get swapped.
            proposal.status = TradeStatus.PENDING_APPROVAL
            proposal.decided_at = datetime.now(UTC)
            self._session.flush()
            self._add_audit(
                league_access.league.id,
                league_access.user.id,
                LeagueAuditAction.MARKET_TRADE_ACCEPTED,
                details={"proposalId": str(proposal.id), "pendingApproval": True},
            )
            self._notify_trade_status(
                proposal_id=proposal.id,
                status=TradeStatus.PENDING_APPROVAL,
                team_ids=[proposer_team.id],
            )
            self._session.commit()
            get_metrics().incr("trade_proposal_accepted_total", labels={"result": "pending"})
            return self._to_response(proposal)

        execute_trade(
            self._session,
            league=league,
            proposal=proposal,
            proposer_team=proposer_team,
            recipient_team=recipient_team,
            actor_id=league_access.user.id,
        )
        proposal.status = TradeStatus.ACCEPTED
        proposal.decided_at = datetime.now(UTC)
        self._session.flush()
        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_TRADE_ACCEPTED,
            details={
                "proposalId": str(proposal.id),
                "proposerTeamId": str(proposer_team.id),
                "recipientTeamId": str(recipient_team.id),
                "offeredAthleteIds": proposal.offered_athlete_ids,
                "requestedAthleteIds": proposal.requested_athlete_ids,
                "offeredCredits": proposal.offered_credits,
                "requestedCredits": proposal.requested_credits,
            },
        )
        self._notify_trade_status(
            proposal_id=proposal.id,
            status=TradeStatus.ACCEPTED,
            team_ids=[proposer_team.id],
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_accepted_total", labels={"result": "executed"})
        return self._to_response(proposal)

    def approve_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
    ) -> TradeProposalResponse:
        """Admin approval (EP08-07): re-validates and executes a pending trade."""
        proposal = self._lock_pending_approval_proposal(proposal_id, league_access)
        league = self._session.get(League, league_access.league.id)
        assert league is not None
        proposer_team = self._session.get(FantasyTeam, proposal.proposer_team_id)
        recipient_team = self._session.get(FantasyTeam, proposal.recipient_team_id)
        assert proposer_team is not None and recipient_team is not None

        execute_trade(
            self._session,
            league=league,
            proposal=proposal,
            proposer_team=proposer_team,
            recipient_team=recipient_team,
            actor_id=league_access.user.id,
        )
        proposal.status = TradeStatus.EXECUTED
        self._session.flush()
        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_TRADE_APPROVED,
            details={"proposalId": str(proposal.id)},
        )
        self._notify_trade_status(
            proposal_id=proposal.id,
            status=TradeStatus.EXECUTED,
            team_ids=[proposer_team.id, recipient_team.id],
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_approved_total")
        return self._to_response(proposal)

    def reject_admin_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
    ) -> TradeProposalResponse:
        proposal = self._lock_pending_approval_proposal(proposal_id, league_access)
        proposal.status = TradeStatus.REJECTED_BY_ADMIN
        self._session.flush()
        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_TRADE_REJECTED_BY_ADMIN,
            details={"proposalId": str(proposal.id)},
        )
        self._notify_trade_status(
            proposal_id=proposal.id,
            status=TradeStatus.REJECTED_BY_ADMIN,
            team_ids=[proposal.proposer_team_id, proposal.recipient_team_id],
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_rejected_by_admin_total")
        return self._to_response(proposal)

    def counter_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
        payload: CounterTradeProposalRequest,
    ) -> TradeProposalResponse:
        team = self._my_team(league_access)
        original = self._lock_actionable_proposal_as_recipient(proposal_id, league_access, team)
        original_proposer = self._session.get(FantasyTeam, original.proposer_team_id)
        assert original_proposer is not None

        # The counter flips the roles: today's recipient proposes back to the
        # original proposer.
        counter = self._build_validated_proposal(
            league_id=league_access.league.id,
            proposer=team,
            recipient=original_proposer,
            offered_athlete_ids_raw=payload.offered_athlete_ids,
            requested_athlete_ids_raw=payload.requested_athlete_ids,
            offered_credits=payload.offered_credits,
            requested_credits=payload.requested_credits,
            expires_at_raw=payload.expires_at,
            created_by=league_access.user.id,
        )
        counter.counter_of_id = original.id
        self._session.add(counter)
        original.status = TradeStatus.COUNTERED
        original.decided_at = datetime.now(UTC)
        self._session.flush()
        self._add_audit(
            league_access.league.id,
            league_access.user.id,
            LeagueAuditAction.MARKET_TRADE_COUNTERED,
            details={
                "originalProposalId": str(original.id),
                "counterProposalId": str(counter.id),
            },
        )
        self._notify_trade_status(
            proposal_id=counter.id,
            status=TradeStatus.COUNTERED,
            team_ids=[original_proposer.id],
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_countered_total")
        return self._to_response(counter)

    def list_proposals(self, league_access: LeagueAccess) -> TradeProposalListResponse:
        team = self._my_team(league_access)
        rows = self._session.scalars(
            select(TradeProposal)
            .where(
                TradeProposal.league_id == league_access.league.id,
                or_(
                    TradeProposal.proposer_team_id == team.id,
                    TradeProposal.recipient_team_id == team.id,
                ),
            )
            .order_by(TradeProposal.created_at.desc())
        ).all()
        return TradeProposalListResponse(proposals=[self._to_response(row) for row in rows])

    def get_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
    ) -> TradeProposalResponse:
        team = self._my_team(league_access)
        proposal = self._session.get(TradeProposal, proposal_id)
        if proposal is None or proposal.league_id != league_access.league.id:
            raise ValidationAuthError("Proposta non trovata.", code="trade_proposal_not_found")
        if proposal.proposer_team_id != team.id and proposal.recipient_team_id != team.id:
            raise ValidationAuthError(
                "Non hai accesso a questa proposta di scambio.",
                code="trade_access_forbidden",
            )
        return self._to_response(proposal)

    # -- helpers ----------------------------------------------------------------

    def _lock_actionable_proposal_as_recipient(
        self,
        proposal_id: UUID,
        league_access: LeagueAccess,
        team: FantasyTeam,
    ) -> TradeProposal:
        """Row-lock the proposal and ensure only one valid transition can win.

        Locking before checking status means a concurrent accept/reject/counter on
        the same proposal blocks until the first commits, then sees the now-terminal
        status and fails cleanly — "solo una transizione valida prevale".
        """
        proposal = self._session.scalars(
            select(TradeProposal).where(TradeProposal.id == proposal_id).with_for_update()
        ).first()
        if proposal is None or proposal.league_id != league_access.league.id:
            raise ValidationAuthError("Proposta non trovata.", code="trade_proposal_not_found")
        if proposal.recipient_team_id != team.id:
            raise ValidationAuthError(
                "Solo il destinatario può decidere su questa proposta.",
                code="trade_decision_forbidden",
            )
        now = datetime.now(UTC)
        if effective_trade_status(proposal, now=now) != TradeStatus.PROPOSED:
            raise ValidationAuthError(
                "La proposta non è più decidibile (scaduta o già decisa).",
                code="trade_not_actionable",
            )
        return proposal

    def _lock_pending_approval_proposal(
        self,
        proposal_id: UUID,
        league_access: LeagueAccess,
    ) -> TradeProposal:
        """Row-lock a proposal awaiting admin approval (EP08-07)."""
        proposal = self._session.scalars(
            select(TradeProposal).where(TradeProposal.id == proposal_id).with_for_update()
        ).first()
        if proposal is None or proposal.league_id != league_access.league.id:
            raise ValidationAuthError("Proposta non trovata.", code="trade_proposal_not_found")
        if proposal.status != TradeStatus.PENDING_APPROVAL:
            raise ValidationAuthError(
                "La proposta non è in attesa di approvazione.",
                code="trade_not_pending_approval",
            )
        return proposal

    def _my_team(self, league_access: LeagueAccess) -> FantasyTeam:
        membership = self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_access.league.id,
                LeagueMembership.user_id == league_access.user.id,
            )
        )
        if membership is None:
            raise ValidationAuthError(
                "Devi essere partecipante della lega per operare sul mercato.",
                code="membership_required",
            )
        team, _ = ensure_team_for_membership(
            self._session,
            membership,
            name=league_access.user.display_name or "Squadra",
            actor_id=league_access.user.id,
        )
        refreshed = find_team_for_membership(self._session, membership.id)
        assert refreshed is not None
        return refreshed

    def _roster_athlete_ids(self, team_id: UUID) -> set[UUID]:
        rows = self._session.scalars(
            select(FantasyRosterSlot.athlete_id).where(
                FantasyRosterSlot.fantasy_team_id == team_id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
        ).all()
        return {row for row in rows if row is not None}

    def _count_active_proposals(self, proposer_team_id: UUID) -> int:
        now = datetime.now(UTC)
        rows = self._session.scalars(
            select(TradeProposal).where(
                TradeProposal.proposer_team_id == proposer_team_id,
                TradeProposal.status == TradeStatus.PROPOSED,
                TradeProposal.expires_at > now,
            )
        ).all()
        return len(rows)

    def _add_audit(
        self,
        league_id: UUID,
        actor_id: UUID,
        action: LeagueAuditAction,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            LeagueAuditEvent(league_id=league_id, actor_id=actor_id, action=action, details=details)
        )
        self._session.flush()

    def _notify_trade_status(
        self,
        *,
        proposal_id: UUID,
        status: TradeStatus,
        team_ids: list[UUID],
    ) -> None:
        recipients = user_ids_for_teams(self._session, team_ids)
        notifications = NotificationService(self._session)
        for user_id in recipients.values():
            notifications.create_notification(
                user_id=user_id,
                category=NotificationCategory.MERCATO,
                template_key="mercato.scambio",
                template_version=1,
                params={"status": status.value},
                dedup_key=f"trade_status:{proposal_id}:{status.value}:{user_id}",
            )

    def _to_response(self, proposal: TradeProposal) -> TradeProposalResponse:
        now = datetime.now(UTC)
        offered = self._athlete_labels(proposal.offered_athlete_ids)
        requested = self._athlete_labels(proposal.requested_athlete_ids)
        return TradeProposalResponse(
            id=str(proposal.id),
            leagueId=str(proposal.league_id),
            proposerTeamId=str(proposal.proposer_team_id),
            recipientTeamId=str(proposal.recipient_team_id),
            offeredAthletes=offered,
            requestedAthletes=requested,
            offeredCredits=proposal.offered_credits,
            requestedCredits=proposal.requested_credits,
            status=effective_trade_status(proposal, now=now).value,
            expiresAt=proposal.expires_at.isoformat(),
            createdAt=proposal.created_at.isoformat(),
            counterOfId=str(proposal.counter_of_id) if proposal.counter_of_id else None,
        )

    def _athlete_labels(self, raw_ids: list[str]) -> list[TradeAthleteResponse]:
        if not raw_ids:
            return []
        ids = [UUID(value) for value in raw_ids]
        rows = self._session.scalars(select(Athlete).where(Athlete.id.in_(ids))).all()
        by_id = {row.id: row for row in rows}
        return [
            TradeAthleteResponse(
                id=str(athlete_id),
                name=by_id[athlete_id].canonical_name if athlete_id in by_id else "Calciatore",
            )
            for athlete_id in ids
        ]
