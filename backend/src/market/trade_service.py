"""Trade proposal service: create, list and cancel (EP08-05 / FR-MKT-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import LeagueAuditAction, TradeStatus
from fantasy_teams.factory import (
    ensure_team_for_membership,
    find_team_by_id,
    find_team_for_membership,
)
from fantasy_teams.ledger import find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from market.models import TradeProposal
from market.trade_schemas import (
    CreateTradeProposalRequest,
    TradeAthleteResponse,
    TradeProposalListResponse,
    TradeProposalResponse,
)
from market.trade_validators import (
    parse_athlete_ids,
    validate_athletes_owned_by_team,
    validate_distinct_teams,
    validate_no_athlete_overlap,
    validate_offered_credits_within_balance,
    validate_trade_expiry,
    validate_trade_sides_not_empty,
    validate_trades_enabled,
)
from market.windows import effective_trade_status
from observability.metrics import get_metrics
from sports_data.roster.models import Athlete

_NEW_AUDIT_ACTION = LeagueAuditAction.MARKET_TRADE_PROPOSED


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
        rules = self._session.scalar(select(LeagueRules).where(LeagueRules.league_id == league_id))
        validate_trades_enabled(allow_trades=rules.allow_trades if rules else True)

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
        validate_distinct_teams(proposer_team_id=proposer.id, recipient_team_id=recipient.id)

        offered_athlete_ids = parse_athlete_ids(payload.offered_athlete_ids, field="offerta")
        requested_athlete_ids = parse_athlete_ids(payload.requested_athlete_ids, field="richiesta")
        validate_no_athlete_overlap(
            offered_athlete_ids=offered_athlete_ids,
            requested_athlete_ids=requested_athlete_ids,
        )
        validate_trade_sides_not_empty(
            offered_athlete_ids=offered_athlete_ids,
            offered_credits=payload.offered_credits,
            requested_athlete_ids=requested_athlete_ids,
            requested_credits=payload.requested_credits,
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

        account = find_account_for_team(self._session, proposer.id)
        balance = account.balance if account is not None else 0
        validate_offered_credits_within_balance(
            offered_credits=payload.offered_credits, balance=balance
        )

        now = datetime.now(UTC)
        expires_at = _parse_required_datetime(payload.expires_at, field="expiresAt")
        validate_trade_expiry(expires_at, now=now)

        proposal = TradeProposal(
            league_id=league_id,
            proposer_team_id=proposer.id,
            recipient_team_id=recipient.id,
            offered_athlete_ids=[str(value) for value in offered_athlete_ids],
            requested_athlete_ids=[str(value) for value in requested_athlete_ids],
            offered_credits=payload.offered_credits,
            requested_credits=payload.requested_credits,
            expires_at=expires_at,
            created_by=league_access.user.id,
        )
        self._session.add(proposal)
        self._session.flush()
        self._add_audit(
            league_id,
            league_access.user.id,
            _NEW_AUDIT_ACTION,
            details={
                "proposalId": str(proposal.id),
                "proposerTeamId": str(proposer.id),
                "recipientTeamId": str(recipient.id),
                "offeredAthleteIds": proposal.offered_athlete_ids,
                "requestedAthleteIds": proposal.requested_athlete_ids,
                "offeredCredits": proposal.offered_credits,
                "requestedCredits": proposal.requested_credits,
                "expiresAt": expires_at.isoformat(),
            },
        )
        self._session.commit()
        get_metrics().incr("trade_proposal_created_total")
        return self._to_response(proposal)

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
