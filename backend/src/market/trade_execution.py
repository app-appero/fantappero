"""Atomic trade execution: re-validate and swap assets on acceptance (EP08-06 / FR-MKT-03).

"Il sistema rivalida tutto al momento dell'accettazione ed esegue in modo atomico" —
every check below re-reads the current, row-locked state (assets may have moved since
the proposal was created) and any failure raises before anything is mutated, so the
caller's transaction rolls back as a whole ("nessuna operazione parziale").
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import CreditLedgerReason, RosterOwnershipSource
from fantasy_teams.composition_service import (
    assign_allowing_role_quota_overflow,
    reconcile_roster_overflow,
    resolve_effective_athlete_roles,
    sync_team_composition_status,
)
from fantasy_teams.ledger import apply_ledger_movement, find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_teams.ownership import sync_ownership_on_assign, sync_ownership_on_release
from leagues.models.league import League
from market.assignment import next_free_slot_or_overflow
from market.models import TradeProposal, TradeReplacement
from market.trade_replacement import net_outgoing_roles, reconcile_trade_replacements
from market.trade_validators import validate_trade_credits_available


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
        .order_by(FantasyRosterSlot.slot_index)
        .with_for_update()
    ).all()
    found_ids = {slot.athlete_id for slot in slots}
    if found_ids != set(athlete_ids):
        raise ValidationAuthError(
            f"Uno o più calciatori {side_label} non sono più nella rosa attesa.",
            code="trade_stale_assets",
        )
    return list(slots)


def execute_trade(
    session: Session,
    *,
    league: League,
    proposal: TradeProposal,
    proposer_team: FantasyTeam,
    recipient_team: FantasyTeam,
    actor_id: UUID | None,
) -> dict[UUID, list[TradeReplacement]]:
    """Re-validate and atomically apply an accepted trade. Raises, never partially applies.

    Ritorna, per squadra, i sostituti da scegliere creati dallo scambio (1.5): una squadra che
    cede più giocatori di quanti ne riceve e resta sotto la misura della rosa deve sceglierne
    subito uno per ogni posto vuoto (`market.trade_replacement`).
    """
    offered_ids = [UUID(value) for value in proposal.offered_athlete_ids]
    requested_ids = [UUID(value) for value in proposal.requested_athlete_ids]

    # Ordine dei blocchi sempre uguale (per id squadra): due scambi che si incrociano
    # sulle stesse due squadre non si bloccano a vicenda (deadlock).
    accounts = {}
    for team in sorted((proposer_team, recipient_team), key=lambda item: str(item.id)):
        accounts[team.id] = find_account_for_team(session, team.id, for_update=True)
    proposer_account = accounts[proposer_team.id]
    recipient_account = accounts[recipient_team.id]

    slots_by_team: dict[UUID, list[FantasyRosterSlot]] = {}
    sides = (
        (proposer_team.id, offered_ids, "offerti dal proponente"),
        (recipient_team.id, requested_ids, "richiesti al destinatario"),
    )
    for team_id, athlete_ids, side_label in sorted(sides, key=lambda item: str(item[0])):
        slots_by_team[team_id] = _locked_slots_for_athletes(
            session, team_id=team_id, athlete_ids=athlete_ids, side_label=side_label
        )
    proposer_out_slots = slots_by_team[proposer_team.id]
    recipient_out_slots = slots_by_team[recipient_team.id]

    validate_trade_credits_available(
        offered_credits=proposal.offered_credits,
        proposer_balance=proposer_account.balance if proposer_account is not None else None,
        requested_credits=proposal.requested_credits,
        recipient_balance=recipient_account.balance if recipient_account is not None else None,
    )
    assert proposer_account is not None and recipient_account is not None

    # Everything below actually mutates state. It runs inside a savepoint so that a
    # mid-sequence failure (e.g. role quota on a later incoming player) rolls back
    # cleanly on its own — callers in this codebase catch ValidationAuthError at the
    # router layer and return a normal response, so nothing further up the stack is
    # guaranteed to roll back the outer transaction for us.
    # Il prezzo d'acquisto segue il calciatore: lo scambio non muove crediti per i giocatori.
    price_by_athlete: dict[UUID, int] = {
        slot.athlete_id: slot.purchase_credits or 0
        for slot in (*proposer_out_slots, *recipient_out_slots)
        if slot.athlete_id is not None
    }

    # Ruoli di chi esce e di chi entra, letti prima di muovere nulla: servono a scegliere il
    # ruolo del sostituto quando le quote non bastano a deciderlo (il «ceduto in più»).
    trade_roles = {
        athlete_id: item.role
        for athlete_id, item in resolve_effective_athlete_roles(
            session,
            league_id=league.id,
            athlete_ids=[*offered_ids, *requested_ids],
            season_year=league.season_year,
        ).items()
    }

    with session.begin_nested():
        # Release every outgoing player first, freeing slots for both sides. Chi esce lascia
        # anche le formazioni dei turni non ancora iniziati (sync_ownership_on_release).
        for team_id, out_slots in (
            (proposer_team.id, proposer_out_slots),
            (recipient_team.id, recipient_out_slots),
        ):
            for slot in out_slots:
                released_athlete_id = slot.athlete_id
                slot.athlete_id = None
                slot.purchase_credits = None
                slot.exceeds_role_quota = False
                sync_ownership_on_release(
                    session,
                    fantasy_team_id=team_id,
                    slot_index=slot.slot_index,
                    athlete_id=released_athlete_id,
                    actor_id=actor_id,
                )
        session.flush()

        # Assign incoming players one at a time; each role-quota check sees the
        # cumulative effect of the steps already applied within this savepoint.
        for athlete_id in requested_ids:
            slot, overflow_capacity = next_free_slot_or_overflow(
                session, team_id=proposer_team.id, league_id=league.id
            )
            # Chi si scambia è già nella lega: vale il ruolo con cui lo conta la rosa che lo
            # cede, anche se non è più nel listone di quest'anno (``require_listone=False``).
            _, exceeds_quota = assign_allowing_role_quota_overflow(
                session,
                league=league,
                team=proposer_team,
                athlete_id=athlete_id,
                slot_index=slot.slot_index,
                require_listone=False,
            )
            slot.athlete_id = athlete_id
            slot.purchase_credits = price_by_athlete.get(athlete_id, 0)
            slot.exceeds_role_quota = exceeds_quota or overflow_capacity
            session.flush()
            sync_ownership_on_assign(
                session,
                league_id=league.id,
                fantasy_team_id=proposer_team.id,
                slot_index=slot.slot_index,
                athlete_id=athlete_id,
                purchase_credits=price_by_athlete.get(athlete_id, 0),
                source=RosterOwnershipSource.MARKET,
                previous_athlete_id=None,
            )
        for athlete_id in offered_ids:
            slot, overflow_capacity = next_free_slot_or_overflow(
                session, team_id=recipient_team.id, league_id=league.id
            )
            _, exceeds_quota = assign_allowing_role_quota_overflow(
                session,
                league=league,
                team=recipient_team,
                athlete_id=athlete_id,
                slot_index=slot.slot_index,
                require_listone=False,
            )
            slot.athlete_id = athlete_id
            slot.purchase_credits = price_by_athlete.get(athlete_id, 0)
            slot.exceeds_role_quota = exceeds_quota or overflow_capacity
            session.flush()
            sync_ownership_on_assign(
                session,
                league_id=league.id,
                fantasy_team_id=recipient_team.id,
                slot_index=slot.slot_index,
                athlete_id=athlete_id,
                purchase_credits=price_by_athlete.get(athlete_id, 0),
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

        # Chi ha ceduto giocatori può essere rientrato nei limiti: sblocca chi
        # era in attesa solo per un esubero ormai risolto (EP08-10).
        session.flush()
        reconcile_roster_overflow(session, league=league, team=proposer_team)
        reconcile_roster_overflow(session, league=league, team=recipient_team)
        # Chi cede più giocatori di quanti ne riceve e resta sotto la misura della rosa ha
        # diritto a un sostituto per ogni posto vuoto (1.5, decisione del 25/11).
        created: dict[UUID, list[TradeReplacement]] = {}
        for team, outgoing, incoming in (
            (proposer_team, offered_ids, requested_ids),
            (recipient_team, requested_ids, offered_ids),
        ):
            created[team.id] = reconcile_trade_replacements(
                session,
                league=league,
                team=team,
                trade=proposal,
                new_allowance=len(outgoing) - len(incoming),
                preferred_roles=net_outgoing_roles(
                    [trade_roles.get(athlete_id) for athlete_id in outgoing],
                    [trade_roles.get(athlete_id) for athlete_id in incoming],
                ),
            )
        # Lo stato salvato segue sempre la regola delle letture della rosa: una squadra
        # rimasta a 34/35 è "incompleta", non "non valida" (`sync_team_composition_status`).
        sync_team_composition_status(session, proposer_team, league=league)
        sync_team_composition_status(session, recipient_team, league=league)
    return created
