"""Apply a winning auction bid to a roster, reusing fantasy_teams primitives (EP08-02)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import CreditLedgerReason, RosterOwnershipSource
from fantasy_teams.composition_service import (
    assert_assignment_respects_role_quota,
    assign_allowing_role_quota_overflow,
    resolve_effective_athlete_role,
    sync_team_composition_status,
)
from fantasy_teams.ledger import apply_ledger_movement, find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_teams.ownership import sync_ownership_on_assign
from leagues.models.league import League


def next_free_slot_or_overflow(
    session: Session, *, team_id: UUID, league_id: UUID
) -> tuple[FantasyRosterSlot, bool]:
    """Returns `(slot, created_new)`. A genuinely free slot is reused when one
    exists; otherwise (EP08-10 bis: rosa già al completo) an extra slot is
    created rather than refusing the acquisition — the incoming player stays in
    the squad but blocked until the coach releases someone."""
    slot = session.scalar(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.fantasy_team_id == team_id,
            FantasyRosterSlot.athlete_id.is_(None),
        )
        .order_by(FantasyRosterSlot.slot_index.asc())
        .with_for_update()
    )
    if slot is not None:
        return slot, False
    max_index = session.scalar(
        select(func.max(FantasyRosterSlot.slot_index)).where(
            FantasyRosterSlot.fantasy_team_id == team_id
        )
    )
    new_slot = FantasyRosterSlot(
        fantasy_team_id=team_id,
        league_id=league_id,
        slot_index=(max_index if max_index is not None else -1) + 1,
    )
    session.add(new_slot)
    session.flush()
    return new_slot, True


def _finalize_slot_assignment(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    slot: FantasyRosterSlot,
    acquire_athlete_id: UUID,
    previous_athlete_id: UUID | None,
    amount_credits: int,
    reason: CreditLedgerReason,
    transaction_id: str,
    actor_id: UUID | None,
    note: str,
    allow_overflow: bool = False,
    force_overflow_flag: bool = False,
) -> FantasyRosterSlot | None:
    account = find_account_for_team(session, team.id, for_update=True)
    if account is None or account.balance < amount_credits:
        return None

    exceeds_quota = False
    try:
        if allow_overflow:
            _, exceeds_quota = assign_allowing_role_quota_overflow(
                session,
                league=league,
                team=team,
                athlete_id=acquire_athlete_id,
                slot_index=slot.slot_index,
            )
        else:
            assert_assignment_respects_role_quota(
                session,
                league=league,
                team=team,
                athlete_id=acquire_athlete_id,
                slot_index=slot.slot_index,
            )
    except ValidationAuthError:
        return None

    try:
        with session.begin_nested():
            slot.athlete_id = acquire_athlete_id
            slot.purchase_credits = amount_credits
            slot.exceeds_role_quota = exceeds_quota or force_overflow_flag
            session.flush()
    except IntegrityError:
        return None

    apply_ledger_movement(
        session,
        account,
        amount=-amount_credits,
        reason=reason,
        transaction_id=transaction_id,
        actor_id=actor_id,
        note=note,
    )
    sync_ownership_on_assign(
        session,
        league_id=league.id,
        fantasy_team_id=team.id,
        slot_index=slot.slot_index,
        athlete_id=acquire_athlete_id,
        purchase_credits=amount_credits,
        source=RosterOwnershipSource.MARKET,
        previous_athlete_id=previous_athlete_id,
    )
    sync_team_composition_status(session, team, league=league)
    return slot


def assign_winning_bid(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    athlete_id: UUID,
    amount_credits: int,
    transaction_id: str,
    actor_id: UUID | None,
    allow_overflow: bool = False,
) -> FantasyRosterSlot | None:
    """Assign an auction-won athlete to the team's first free slot.

    Returns the updated slot on success, or ``None`` when the assignment
    cannot be honored (no free slot, insufficient credits, or role quota
    exceeded) — those are legitimate "lost bid" outcomes per FR-AST-01
    ("segnala le rose ancora incomplete"), not fatal errors.

    With ``allow_overflow`` (sealed-bid auction, EP08-10 bis) a full roster or
    an exceeded role quota no longer loses the bid: the player is assigned,
    flagged as in excess, and waits for the coach to release someone.
    """
    if allow_overflow:
        try:
            with session.begin_nested():
                overflow_slot, created_new = next_free_slot_or_overflow(
                    session, team_id=team.id, league_id=league.id
                )
                result = _finalize_slot_assignment(
                    session,
                    league=league,
                    team=team,
                    slot=overflow_slot,
                    acquire_athlete_id=athlete_id,
                    previous_athlete_id=None,
                    amount_credits=amount_credits,
                    reason=CreditLedgerReason.MARKET_AUCTION_WIN,
                    transaction_id=transaction_id,
                    actor_id=actor_id,
                    note="Assegnazione da asta a buste",
                    allow_overflow=True,
                    force_overflow_flag=created_new,
                )
                if result is None:
                    raise _SwapNotHonored
        except _SwapNotHonored:
            return None
        return result
    slot = session.scalar(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.fantasy_team_id == team.id,
            FantasyRosterSlot.athlete_id.is_(None),
        )
        .order_by(FantasyRosterSlot.slot_index.asc())
        .with_for_update()
    )
    if slot is None:
        return None
    return _finalize_slot_assignment(
        session,
        league=league,
        team=team,
        slot=slot,
        acquire_athlete_id=athlete_id,
        previous_athlete_id=None,
        amount_credits=amount_credits,
        reason=CreditLedgerReason.MARKET_AUCTION_WIN,
        transaction_id=transaction_id,
        actor_id=actor_id,
        note="Assegnazione da asta a buste",
    )


class _SwapNotHonored(Exception):
    """Internal sentinel: rolls back the swap's savepoint via ``begin_nested``."""


def resolve_live_swap(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    release_athlete_id: UUID,
    acquire_athlete_id: UUID,
    amount_credits: int,
    transaction_id: str,
    refund_transaction_id: str,
    actor_id: UUID | None,
) -> FantasyRosterSlot | None:
    """Resolve a live-auction roster-full swap prompt (EP08-09).

    The coach releases ``release_athlete_id`` (refunded in full — this is a
    forced choice created by winning a lot with no room, not a voluntary
    release, so the usual partial-refund rule doesn't apply) and the newly
    won ``acquire_athlete_id`` takes its slot. The refund is applied before
    the acquisition charge so a refund that covers the gap can fund the win;
    both happen in a savepoint so a failed swap (slot changed underneath,
    role quota violated) undoes the refund too. Returns ``None`` — not a
    fatal error — if the declared slot no longer holds that athlete or the
    swap can't be honored.
    """
    slot = session.scalar(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.fantasy_team_id == team.id,
            FantasyRosterSlot.athlete_id == release_athlete_id,
        )
        .with_for_update()
    )
    if slot is None:
        return None
    account = find_account_for_team(session, team.id, for_update=True)
    if account is None:
        return None
    refund_credits = slot.purchase_credits or 0

    # Scambio dello stesso ruolo: non peggiora la composizione, quindi non può essere
    # respinto per quota anche se il ruolo è già in sovrannumero (il flag resta acceso).
    competition_ids = {competition.id for competition in league.competitions}
    released_role = resolve_effective_athlete_role(
        session,
        league_id=league.id,
        athlete_id=release_athlete_id,
        season_year=league.season_year,
        competition_ids=competition_ids,
    )
    acquired_role = resolve_effective_athlete_role(
        session,
        league_id=league.id,
        athlete_id=acquire_athlete_id,
        season_year=league.season_year,
        competition_ids=competition_ids,
    )
    same_role = released_role is not None and released_role == acquired_role

    try:
        with session.begin_nested():
            if refund_credits > 0:
                apply_ledger_movement(
                    session,
                    account,
                    amount=refund_credits,
                    reason=CreditLedgerReason.MARKET_RELEASE_REFUND,
                    transaction_id=refund_transaction_id,
                    actor_id=actor_id,
                    note="Rimborso per scambio da asta a rilanci (rosa al completo)",
                )
            updated = _finalize_slot_assignment(
                session,
                league=league,
                team=team,
                slot=slot,
                acquire_athlete_id=acquire_athlete_id,
                previous_athlete_id=release_athlete_id,
                amount_credits=amount_credits,
                reason=CreditLedgerReason.MARKET_AUCTION_WIN,
                transaction_id=transaction_id,
                actor_id=actor_id,
                note="Scambio da asta a rilanci (rosa al completo)",
                allow_overflow=same_role,
            )
            if updated is None:
                raise _SwapNotHonored
    except _SwapNotHonored:
        return None
    return updated


def assign_winning_waiver_bid(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    acquire_athlete_id: UUID,
    release_athlete_id: UUID,
    amount_credits: int,
    transaction_id: str,
    actor_id: UUID | None,
) -> FantasyRosterSlot | None:
    """Swap a waiver-won free agent in for the bid's declared release (EP08-03).

    The release and the acquisition happen atomically on the same roster slot:
    if the swap would leave an invalid roster (role quota) or the declared
    player is no longer on the team's roster, nothing is changed and the bid
    is a legitimate loss ("cambio annullato se crea rosa invalida" / FR-MKT-01),
    not a fatal error. No credit refund is applied for the released player —
    that is EP08-04's scope.
    """
    slot = session.scalar(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.fantasy_team_id == team.id,
            FantasyRosterSlot.athlete_id == release_athlete_id,
        )
        .with_for_update()
    )
    if slot is None:
        return None
    return _finalize_slot_assignment(
        session,
        league=league,
        team=team,
        slot=slot,
        acquire_athlete_id=acquire_athlete_id,
        previous_athlete_id=release_athlete_id,
        amount_credits=amount_credits,
        reason=CreditLedgerReason.MARKET_WAIVER_ACQUISITION,
        transaction_id=transaction_id,
        actor_id=actor_id,
        note="Acquisizione da mercato svincolati",
    )
