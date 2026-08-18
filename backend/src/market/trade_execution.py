"""Atomic trade execution: re-validate and swap assets on acceptance (EP08-06 / FR-MKT-03).

"Il sistema rivalida tutto al momento dell'accettazione ed esegue in modo atomico" —
every check below re-reads the current, row-locked state (assets may have moved since
the proposal was created) and any failure raises before anything is mutated, so the
caller's transaction rolls back as a whole ("nessuna operazione parziale").
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import CreditLedgerReason, RosterOwnershipSource
from fantasy_teams.composition_service import (
    assert_assignment_respects_role_quota,
    sync_team_composition_status,
)
from fantasy_teams.ledger import apply_ledger_movement, find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_teams.ownership import sync_ownership_on_assign, sync_ownership_on_release
from leagues.models.league import League
from market.models import TradeProposal


def _locked_slots_for_athletes(
    session: Session, *, team_id: UUID, athlete_ids: list[UUID], side_label: str
) -> list[FantasyRosterSlot]:
    if not athlete_ids:
        return []
    slots = session.scalars(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.fantasy_team_id == team_id,
            FantasyRosterSlot.athlete_id.in_(athlete_ids),
        )
        .with_for_update()
    ).all()
    found_ids = {slot.athlete_id for slot in slots}
    if found_ids != set(athlete_ids):
        raise ValidationAuthError(
            f"Uno o più calciatori {side_label} non sono più nella rosa attesa.",
            code="trade_stale_assets",
        )
    return list(slots)


def _free_slot_count(session: Session, *, team_id: UUID) -> int:
    return (
        session.scalar(
            select(func.count(FantasyRosterSlot.id)).where(
                FantasyRosterSlot.fantasy_team_id == team_id,
                FantasyRosterSlot.athlete_id.is_(None),
            )
        )
        or 0
    )


def _next_free_slot(session: Session, *, team_id: UUID) -> FantasyRosterSlot:
    slot = session.scalar(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.fantasy_team_id == team_id,
            FantasyRosterSlot.athlete_id.is_(None),
        )
        .order_by(FantasyRosterSlot.slot_index.asc())
        .with_for_update()
    )
    if slot is None:
        raise ValidationAuthError(
            "La rosa non ha più slot liberi per completare lo scambio.",
            code="trade_roster_full",
        )
    return slot


def execute_trade(
    session: Session,
    *,
    league: League,
    proposal: TradeProposal,
    proposer_team: FantasyTeam,
    recipient_team: FantasyTeam,
    actor_id: UUID | None,
) -> None:
    """Re-validate and atomically apply an accepted trade. Raises, never partially applies."""
    offered_ids = [UUID(value) for value in proposal.offered_athlete_ids]
    requested_ids = [UUID(value) for value in proposal.requested_athlete_ids]

    proposer_out_slots = _locked_slots_for_athletes(
        session,
        team_id=proposer_team.id,
        athlete_ids=offered_ids,
        side_label="offerti dal proponente",
    )
    recipient_out_slots = _locked_slots_for_athletes(
        session,
        team_id=recipient_team.id,
        athlete_ids=requested_ids,
        side_label="richiesti al destinatario",
    )

    proposer_account = find_account_for_team(session, proposer_team.id, for_update=True)
    recipient_account = find_account_for_team(session, recipient_team.id, for_update=True)
    if proposer_account is None or proposer_account.balance < proposal.offered_credits:
        raise ValidationAuthError(
            "Il proponente non ha più crediti sufficienti per lo scambio.",
            code="insufficient_credits",
        )
    if recipient_account is None or recipient_account.balance < proposal.requested_credits:
        raise ValidationAuthError(
            "Il destinatario non ha più crediti sufficienti per lo scambio.",
            code="insufficient_credits",
        )

    proposer_extra_needed = max(0, len(requested_ids) - len(offered_ids))
    recipient_extra_needed = max(0, len(offered_ids) - len(requested_ids))
    if _free_slot_count(session, team_id=proposer_team.id) < proposer_extra_needed:
        raise ValidationAuthError(
            "La rosa del proponente non ha spazio per completare lo scambio.",
            code="trade_roster_full",
        )
    if _free_slot_count(session, team_id=recipient_team.id) < recipient_extra_needed:
        raise ValidationAuthError(
            "La rosa del destinatario non ha spazio per completare lo scambio.",
            code="trade_roster_full",
        )

    # Everything below actually mutates state. It runs inside a savepoint so that a
    # mid-sequence failure (e.g. role quota on a later incoming player) rolls back
    # cleanly on its own — callers in this codebase catch ValidationAuthError at the
    # router layer and return a normal response, so nothing further up the stack is
    # guaranteed to roll back the outer transaction for us.
    with session.begin_nested():
        # Release every outgoing player first, freeing slots for both sides.
        for slot in proposer_out_slots:
            slot.athlete_id = None
            slot.purchase_credits = None
            sync_ownership_on_release(
                session, fantasy_team_id=proposer_team.id, slot_index=slot.slot_index
            )
        for slot in recipient_out_slots:
            slot.athlete_id = None
            slot.purchase_credits = None
            sync_ownership_on_release(
                session, fantasy_team_id=recipient_team.id, slot_index=slot.slot_index
            )
        session.flush()

        # Assign incoming players one at a time; each role-quota check sees the
        # cumulative effect of the steps already applied within this savepoint.
        for athlete_id in requested_ids:
            slot = _next_free_slot(session, team_id=proposer_team.id)
            assert_assignment_respects_role_quota(
                session,
                league=league,
                team=proposer_team,
                athlete_id=athlete_id,
                slot_index=slot.slot_index,
            )
            slot.athlete_id = athlete_id
            slot.purchase_credits = 0
            session.flush()
            sync_ownership_on_assign(
                session,
                league_id=league.id,
                fantasy_team_id=proposer_team.id,
                slot_index=slot.slot_index,
                athlete_id=athlete_id,
                purchase_credits=0,
                source=RosterOwnershipSource.MARKET,
                previous_athlete_id=None,
            )
        for athlete_id in offered_ids:
            slot = _next_free_slot(session, team_id=recipient_team.id)
            assert_assignment_respects_role_quota(
                session,
                league=league,
                team=recipient_team,
                athlete_id=athlete_id,
                slot_index=slot.slot_index,
            )
            slot.athlete_id = athlete_id
            slot.purchase_credits = 0
            session.flush()
            sync_ownership_on_assign(
                session,
                league_id=league.id,
                fantasy_team_id=recipient_team.id,
                slot_index=slot.slot_index,
                athlete_id=athlete_id,
                purchase_credits=0,
                source=RosterOwnershipSource.MARKET,
                previous_athlete_id=None,
            )

        if proposal.offered_credits > 0:
            apply_ledger_movement(
                session,
                proposer_account,
                amount=-proposal.offered_credits,
                reason=CreditLedgerReason.MARKET_TRADE_CREDITS_SENT,
                transaction_id=f"trade-sent:{proposal.id}:{proposer_team.id}",
                actor_id=actor_id,
                note="Crediti inviati per scambio",
            )
            apply_ledger_movement(
                session,
                recipient_account,
                amount=proposal.offered_credits,
                reason=CreditLedgerReason.MARKET_TRADE_CREDITS_RECEIVED,
                transaction_id=f"trade-received:{proposal.id}:{recipient_team.id}",
                actor_id=actor_id,
                note="Crediti ricevuti da scambio",
            )
        if proposal.requested_credits > 0:
            apply_ledger_movement(
                session,
                recipient_account,
                amount=-proposal.requested_credits,
                reason=CreditLedgerReason.MARKET_TRADE_CREDITS_SENT,
                transaction_id=f"trade-sent:{proposal.id}:{recipient_team.id}",
                actor_id=actor_id,
                note="Crediti inviati per scambio",
            )
            apply_ledger_movement(
                session,
                proposer_account,
                amount=proposal.requested_credits,
                reason=CreditLedgerReason.MARKET_TRADE_CREDITS_RECEIVED,
                transaction_id=f"trade-received:{proposal.id}:{proposer_team.id}",
                actor_id=actor_id,
                note="Crediti ricevuti da scambio",
            )

        sync_team_composition_status(session, proposer_team, league=league)
        sync_team_composition_status(session, recipient_team, league=league)
