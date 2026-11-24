"""Trade proposal service: create, list and cancel (EP08-05 / FR-MKT-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    LeagueMemberRole,
    NotificationCategory,
    TradeStatus,
)
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
from market.gate import assert_trade_market_open
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
    validate_requested_credits_within_balance,
    validate_trade_credits_available,
    validate_trade_expiry,
    validate_trade_involves_athletes,
    validate_trade_sides_not_empty,
    validate_trades_enabled,
)
from market.valuation_service import LeagueMarketInfoCache
from market.windows import effective_trade_status
from notifications.league_context import league_params
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
    try:
        return parsed.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise ValidationAuthError(
            f"Il campo {field} non è una data valida.",
            code="invalid_datetime",
        ) from exc


def _parse_optional_datetime(value: str | None, *, field: str) -> datetime | None:
    """A blank/absent expiry means the proposal never expires on its own."""
    if value is None or not value.strip():
        return None
    return _parse_required_datetime(value, field=field)


_MONTHS_IT = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")


class TradeService:
    def __init__(self, session: Session) -> None:
        self._session = session
        # Valore e media stagionale dei calciatori della proposta (1.3), una lettura per lega.
        self._market_info = LeagueMarketInfoCache(session)

    def create_proposal(
        self,
        league_access: LeagueAccess,
        payload: CreateTradeProposalRequest,
    ) -> TradeProposalResponse:
        league_id = league_access.league.id
        # Proposta, controproposta, accettazione e approvazione: solo a lega al completo (20/11)
        # e fuori dal turno in corso. Rifiutare o annullare resta sempre possibile.
        assert_trade_market_open(self._session, league_id)
        proposer = self._my_team(league_access)
        # Il blocco del conto serializza le proposte della stessa squadra (limite proposte attive).
        find_account_for_team(self._session, proposer.id, for_update=True)
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
                "expiresAt": proposal.expires_at.isoformat() if proposal.expires_at else None,
            },
        )
        self._notify_trade_status(
            proposal_id=proposal.id,
            status=TradeStatus.PROPOSED,
            team_ids=[recipient.id],
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
        expires_at_raw: str | None,
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
        validate_trade_involves_athletes(
            offered_athlete_ids=offered_athlete_ids,
            requested_athlete_ids=requested_athlete_ids,
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
        recipient_account = find_account_for_team(self._session, recipient.id)
        validate_requested_credits_within_balance(
            requested_credits=requested_credits,
            balance=recipient_account.balance if recipient_account is not None else 0,
        )

        now = datetime.now(UTC)
        expires_at = _parse_optional_datetime(expires_at_raw, field="expiresAt")
        if expires_at is not None:
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
        current = effective_trade_status(proposal, now=now)
        # In attesa dell'amministratore il proponente non può ritirarsi, salvo che lo scambio
        # non sia più eseguibile (calciatori spostati): allora toglierlo di mezzo è l'unica via.
        stale_pending = current == TradeStatus.PENDING_APPROVAL and self._is_stale(proposal)
        if current != TradeStatus.PROPOSED and not stale_pending:
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
        self._notify_trade_status(
            proposal_id=proposal.id,
            status=TradeStatus.CANCELLED,
            team_ids=[proposal.recipient_team_id],
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
        assert_trade_market_open(self._session, league_access.league.id)
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
            # Deferred to admin approval (EP08-07): nothing is moved yet — execute_trade
            # re-validates everything fresh at approval time, when the assets get swapped.
            # I crediti però si guardano già ora, come nell'accettazione senza approvazione
            # (KI-21, 24/11): una proposta "in attesa di crediti" non conta nel limite delle
            # proposte attive, in attesa dell'amministratore conterebbe e farebbe superare il
            # limite a chi l'ha proposta. Resta aperta e si accetta quando i crediti tornano.
            proposer_account = find_account_for_team(self._session, proposal.proposer_team_id)
            recipient_account = find_account_for_team(self._session, proposal.recipient_team_id)
            validate_trade_credits_available(
                offered_credits=proposal.offered_credits,
                proposer_balance=proposer_account.balance if proposer_account else None,
                requested_credits=proposal.requested_credits,
                recipient_balance=recipient_account.balance if recipient_account else None,
            )
            proposal.status = TradeStatus.PENDING_APPROVAL
            proposal.decided_at = datetime.now(UTC)
            self._session.flush()
            self._add_audit(
                league_access.league.id,
                league_access.user.id,
                LeagueAuditAction.MARKET_TRADE_ACCEPTED,
                details={"proposalId": str(proposal.id), "pendingApproval": True},
            )
            # Un avviso per evento e mai a chi ha appena accettato: l'amministratore che è
            # parte dello scambio riceve solo "da approvare" (e nulla se ha accettato lui).
            admin_ids = self._notify_admins_trade_pending(
                proposal,
                proposer_team,
                recipient_team,
                exclude_user_ids={league_access.user.id},
            )
            self._notify_trade_status(
                proposal_id=proposal.id,
                status=TradeStatus.PENDING_APPROVAL,
                team_ids=[proposer_team.id],
                exclude_user_ids=admin_ids | {league_access.user.id},
            )
            self._session.commit()
            get_metrics().incr("trade_proposal_accepted_total", labels={"result": "pending"})
            return self._to_response(proposal)

        self._execute_or_expire(
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
        assert_trade_market_open(self._session, league_access.league.id)
        proposal = self._lock_pending_approval_proposal(proposal_id, league_access)
        league = self._session.get(League, league_access.league.id)
        assert league is not None
        proposer_team = self._session.get(FantasyTeam, proposal.proposer_team_id)
        recipient_team = self._session.get(FantasyTeam, proposal.recipient_team_id)
        assert proposer_team is not None and recipient_team is not None

        self._execute_or_expire(
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
            details={
                "proposalId": str(proposal.id),
                # L'admin può approvare uno scambio in cui è parte: resta scritto nel registro.
                "approverIsParty": league_access.user.id
                in set(
                    user_ids_for_teams(
                        self._session, [proposer_team.id, recipient_team.id]
                    ).values()
                ),
            },
        )
        self._notify_trade_status(
            proposal_id=proposal.id,
            status=TradeStatus.EXECUTED,
            team_ids=[proposer_team.id, recipient_team.id],
            exclude_user_ids={league_access.user.id},
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
            exclude_user_ids={league_access.user.id},
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
        assert_trade_market_open(self._session, league_access.league.id)
        team = self._my_team(league_access)
        original = self._lock_actionable_proposal_as_recipient(proposal_id, league_access, team)
        # Conto bloccato dopo la proposta, nello stesso ordine di accetta e annulla.
        find_account_for_team(self._session, team.id, for_update=True)
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
        team = self._my_team_or_none(league_access)
        conditions = []
        if team is not None:
            conditions.extend(
                [
                    TradeProposal.proposer_team_id == team.id,
                    TradeProposal.recipient_team_id == team.id,
                ]
            )
        if self._can_review_trades(league_access):
            # N3: chi deve approvare vede gli scambi in attesa, anche se non sono suoi.
            conditions.append(TradeProposal.status == TradeStatus.PENDING_APPROVAL)
        if not conditions:
            raise ValidationAuthError(
                "Devi essere partecipante della lega per operare sul mercato.",
                code="membership_required",
            )
        rows = self._session.scalars(
            select(TradeProposal)
            .where(TradeProposal.league_id == league_access.league.id, or_(*conditions))
            .order_by(TradeProposal.created_at.desc())
        ).all()
        by_league: dict[UUID, list[UUID]] = {}
        for row in rows:
            by_league.setdefault(row.league_id, []).extend(
                UUID(value) for value in [*row.offered_athlete_ids, *row.requested_athlete_ids]
            )
        for league_id, athlete_ids in by_league.items():
            self._market_info.get(league_id, athlete_ids)  # una lettura per tutta la lista
        return TradeProposalListResponse(proposals=[self._to_response(row) for row in rows])

    def get_proposal(
        self,
        league_access: LeagueAccess,
        proposal_id: UUID,
    ) -> TradeProposalResponse:
        team = self._my_team_or_none(league_access)
        proposal = self._session.get(TradeProposal, proposal_id)
        if proposal is None or proposal.league_id != league_access.league.id:
            raise ValidationAuthError("Proposta non trovata.", code="trade_proposal_not_found")
        is_party = team is not None and team.id in (
            proposal.proposer_team_id,
            proposal.recipient_team_id,
        )
        # Chi approva gli scambi può aprirli sempre (anche dopo la decisione): serve al link
        # della notifica "Scambio da approvare".
        is_reviewer = self._can_review_trades(league_access)
        if not is_party and not is_reviewer:
            raise ValidationAuthError(
                "Non hai accesso a questa proposta di scambio.",
                code="trade_access_forbidden",
            )
        return self._to_response(proposal)

    def _can_review_trades(self, league_access: LeagueAccess) -> bool:
        return (
            league_access.operator_bypass or league_access.membership_role == LeagueMemberRole.OWNER
        )

    def _my_team_or_none(self, league_access: LeagueAccess) -> FantasyTeam | None:
        try:
            return self._my_team(league_access)
        except ValidationAuthError:
            if self._can_review_trades(league_access):
                return None
            raise

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
        # Lettura senza blocchi: bloccare qui il conto crediti di chi agisce, prima della
        # proposta, provocava deadlock fra accettazioni incrociate e "accetta + annulla".
        existing = find_team_for_membership(self._session, membership.id)
        if existing is not None and find_account_for_team(self._session, existing.id) is not None:
            return existing
        ensure_team_for_membership(
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
                or_(
                    and_(
                        TradeProposal.status == TradeStatus.PROPOSED,
                        # No expiry means the proposal never expires on its own — still active.
                        or_(TradeProposal.expires_at.is_(None), TradeProposal.expires_at > now),
                    ),
                    # KI-21 (Rosario 24/11): accettata e in attesa dell'amministratore è ancora
                    # attiva fino alla sua decisione (e non scade con l'orario della proposta).
                    TradeProposal.status == TradeStatus.PENDING_APPROVAL,
                ),
            )
        ).all()
        # Non occupano il limite né le proposte in attesa di crediti né quelle non più eseguibili.
        return sum(1 for row in rows if not self._awaiting_credits(row) and not self._is_stale(row))

    def _awaiting_credits(self, proposal: TradeProposal) -> bool:
        """True se il saldo di chi offre o di chi riceve non copre i crediti della proposta."""
        if proposal.status != TradeStatus.PROPOSED:
            return False
        if proposal.offered_credits <= 0 and proposal.requested_credits <= 0:
            return False
        proposer = find_account_for_team(self._session, proposal.proposer_team_id)
        recipient = find_account_for_team(self._session, proposal.recipient_team_id)
        proposer_balance = proposer.balance if proposer is not None else 0
        recipient_balance = recipient.balance if recipient is not None else 0
        return (
            proposal.offered_credits > proposer_balance
            or proposal.requested_credits > recipient_balance
        )

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

    def _is_stale(
        self, proposal: TradeProposal, *, rosters: dict[UUID, set[UUID]] | None = None
    ) -> bool:
        """True se i calciatori della proposta non sono più nelle rose attese."""

        def roster(team_id: UUID) -> set[UUID]:
            if rosters is None:
                return self._roster_athlete_ids(team_id)
            if team_id not in rosters:
                rosters[team_id] = self._roster_athlete_ids(team_id)
            return rosters[team_id]

        offered = {UUID(value) for value in proposal.offered_athlete_ids}
        requested = {UUID(value) for value in proposal.requested_athlete_ids}
        return not offered <= roster(proposal.proposer_team_id) or (
            not requested <= roster(proposal.recipient_team_id)
        )

    def expire_overdue_proposals(self, *, now: datetime | None = None, limit: int = 500) -> int:
        """Segna come scadute le proposte oltre la scadenza e avvisa i due allenatori.

        Lo stato "scaduta" è già calcolato in lettura; qui diventa anche persistente così la
        notifica parte una volta sola, anche se nessuno apre l'app.
        """
        moment = now or datetime.now(UTC)
        rows = self._session.scalars(
            select(TradeProposal)
            .where(
                TradeProposal.status == TradeStatus.PROPOSED,
                TradeProposal.expires_at.is_not(None),
                TradeProposal.expires_at <= moment,
            )
            .order_by(TradeProposal.expires_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for proposal in rows:
            proposal.status = TradeStatus.EXPIRED
            proposal.decided_at = moment
            self._session.flush()
            self._notify_trade_status(
                proposal_id=proposal.id,
                status=TradeStatus.EXPIRED,
                team_ids=[proposal.proposer_team_id, proposal.recipient_team_id],
            )
        # Decadute senza scadenza: un calciatore ha lasciato la rosa (svincolo, altro scambio).
        # Si leggono già "scadute"; qui si chiudono, così l'avviso parte anche se nessuno prova
        # ad accettarle. Le proposte "in attesa di crediti" restano aperte: non sono decadute.
        closed = len(rows)
        open_ids = self._session.scalars(
            select(TradeProposal.id)
            .where(
                TradeProposal.status == TradeStatus.PROPOSED,
                or_(TradeProposal.expires_at.is_(None), TradeProposal.expires_at > moment),
            )
            .order_by(TradeProposal.created_at.asc())
        ).all()
        rosters: dict[UUID, set[UUID]] = {}
        for proposal_id in open_ids:
            if closed >= limit:
                break
            candidate = self._session.get(TradeProposal, proposal_id)
            if candidate is None or not self._is_stale(candidate, rosters=rosters):
                continue
            # Blocco e ricontrollo: un accetta/annulla concorrente vince e qui si salta.
            proposal = self._session.scalars(
                select(TradeProposal)
                .where(
                    TradeProposal.id == proposal_id, TradeProposal.status == TradeStatus.PROPOSED
                )
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            ).first()
            if proposal is None or not self._is_stale(proposal):
                continue
            proposal.status = TradeStatus.EXPIRED
            proposal.decided_at = moment
            self._session.flush()
            self._notify_trade_status(
                proposal_id=proposal.id,
                status=TradeStatus.EXPIRED,
                team_ids=[proposal.proposer_team_id, proposal.recipient_team_id],
                no_longer_valid=True,
            )
            closed += 1
        self._session.commit()
        return closed

    def _execute_or_expire(
        self,
        *,
        league: League,
        proposal: TradeProposal,
        proposer_team: FantasyTeam,
        recipient_team: FantasyTeam,
        actor_id: UUID,
    ) -> None:
        """Esegue lo scambio; se i calciatori si sono mossi la proposta non resta in sospeso."""
        try:
            execute_trade(
                self._session,
                league=league,
                proposal=proposal,
                proposer_team=proposer_team,
                recipient_team=recipient_team,
                actor_id=actor_id,
            )
        except ValidationAuthError as exc:
            if exc.code == "trade_stale_assets":
                # 2.4: non più eseguibile per sempre: esce da "Da gestire" e libera il limite.
                proposal.status = TradeStatus.EXPIRED
                proposal.decided_at = datetime.now(UTC)
                self._notify_trade_status(
                    proposal_id=proposal.id,
                    status=TradeStatus.EXPIRED,
                    team_ids=[proposal.proposer_team_id, proposal.recipient_team_id],
                    no_longer_valid=True,
                )
                self._session.commit()
            raise

    def _notify_admins_trade_pending(
        self,
        proposal: TradeProposal,
        proposer_team: FantasyTeam,
        recipient_team: FantasyTeam,
        *,
        exclude_user_ids: set[UUID],
    ) -> set[UUID]:
        """N3: avvisa l'amministratore che c'è uno scambio da approvare.

        Non avvisa chi ha compiuto l'azione; restituisce chi è stato avvisato.
        """
        owner_ids = self._session.scalars(
            select(LeagueMembership.user_id).where(
                LeagueMembership.league_id == proposal.league_id,
                LeagueMembership.role == LeagueMemberRole.OWNER,
            )
        ).all()
        notifications = NotificationService(self._session)
        shared = self._trade_notification_params(proposal)
        notified = {user_id for user_id in owner_ids if user_id not in exclude_user_ids}
        for user_id in notified:
            notifications.create_notification(
                user_id=user_id,
                category=NotificationCategory.MERCATO,
                template_key="mercato.scambio",
                template_version=2,
                params={
                    "status": "admin_review",
                    "other_team": proposer_team.name,
                    "second_team": recipient_team.name,
                    **shared,
                },
                dedup_key=f"trade_status:{proposal.id}:admin_review:{user_id}",
            )
        return notified

    def _notify_trade_status(
        self,
        *,
        proposal_id: UUID,
        status: TradeStatus,
        team_ids: list[UUID],
        exclude_user_ids: set[UUID] | None = None,
        no_longer_valid: bool = False,
    ) -> None:
        recipients = user_ids_for_teams(self._session, team_ids)
        notifications = NotificationService(self._session)
        proposal = self._session.get(TradeProposal, proposal_id)
        shared = self._trade_notification_params(proposal)
        for team_id, user_id in recipients.items():
            if exclude_user_ids and user_id in exclude_user_ids:
                continue
            params: dict[str, object] = {"status": status.value, **shared}
            if no_longer_valid:
                params["no_longer_valid"] = True
            if proposal is not None:
                other_id = (
                    proposal.proposer_team_id
                    if team_id == proposal.recipient_team_id
                    else proposal.recipient_team_id
                )
                other = self._session.get(FantasyTeam, other_id)
                if other is not None:
                    params["other_team"] = other.name
            notifications.create_notification(
                user_id=user_id,
                category=NotificationCategory.MERCATO,
                template_key="mercato.scambio",
                template_version=2,
                params=params,
                dedup_key=f"trade_status:{proposal_id}:{status.value}:{user_id}",
            )

    def _trade_notification_params(self, proposal: TradeProposal | None) -> dict[str, object]:
        """Giocatori, crediti e scadenza da mostrare nel testo della notifica."""
        if proposal is None:
            return {}
        params: dict[str, object] = {
            "proposal_id": str(proposal.id),
            "offered": [row.name for row in self._athlete_labels(proposal.offered_athlete_ids)],
            "requested": [row.name for row in self._athlete_labels(proposal.requested_athlete_ids)],
            "offered_credits": proposal.offered_credits,
            "requested_credits": proposal.requested_credits,
            **league_params(self._session, proposal.league_id),
        }
        if proposal.expires_at is not None:
            local = proposal.expires_at.astimezone(ZoneInfo("Europe/Rome"))
            params["expires_label"] = (
                f"il {local.day} {_MONTHS_IT[local.month - 1]} alle {local:%H:%M}"
            )
        return params

    def _read_status(self, proposal: TradeProposal, now: datetime) -> TradeStatus:
        """Stato mostrato: una proposta 'proposed' non più eseguibile si legge come scaduta."""
        status = effective_trade_status(proposal, now=now)
        if status in (TradeStatus.PROPOSED, TradeStatus.PENDING_APPROVAL) and self._is_stale(
            proposal
        ):
            return TradeStatus.EXPIRED
        return status

    def _to_response(self, proposal: TradeProposal) -> TradeProposalResponse:
        now = datetime.now(UTC)
        offered = self._athlete_labels(proposal.offered_athlete_ids, league_id=proposal.league_id)
        requested = self._athlete_labels(
            proposal.requested_athlete_ids, league_id=proposal.league_id
        )
        return TradeProposalResponse(
            id=str(proposal.id),
            leagueId=str(proposal.league_id),
            proposerTeamId=str(proposal.proposer_team_id),
            recipientTeamId=str(proposal.recipient_team_id),
            offeredAthletes=offered,
            requestedAthletes=requested,
            offeredCredits=proposal.offered_credits,
            requestedCredits=proposal.requested_credits,
            status=(read_status := self._read_status(proposal, now)).value,
            expiresAt=proposal.expires_at.isoformat() if proposal.expires_at else None,
            createdAt=proposal.created_at.isoformat(),
            counterOfId=str(proposal.counter_of_id) if proposal.counter_of_id else None,
            awaitingCredits=read_status == TradeStatus.PROPOSED
            and self._awaiting_credits(proposal),
            noLongerValid=read_status == TradeStatus.EXPIRED
            and not (
                proposal.expires_at is not None
                and proposal.expires_at <= (proposal.decided_at or now)
            ),
        )

    def _athlete_labels(
        self, raw_ids: list[str], *, league_id: UUID | None = None
    ) -> list[TradeAthleteResponse]:
        """Nomi dei calciatori; con ``league_id`` anche Valore e media stagionale (1.3)."""
        if not raw_ids:
            return []
        ids = [UUID(value) for value in raw_ids]
        rows = self._session.scalars(select(Athlete).where(Athlete.id.in_(ids))).all()
        by_id = {row.id: row for row in rows}
        market = self._market_info.get(league_id, ids) if league_id is not None else {}
        return [
            TradeAthleteResponse(
                id=str(athlete_id),
                name=by_id[athlete_id].canonical_name if athlete_id in by_id else "Calciatore",
                marketValue=market[athlete_id].market_value if athlete_id in market else None,
                seasonAverage=market[athlete_id].season_average if athlete_id in market else None,
            )
            for athlete_id in ids
        ]
