"""Apply a winning auction bid to a roster, reusing fantasy_teams primitives (EP08-02)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import CreditLedgerReason, RosterOwnershipSource
from fantasy_teams.composition_service import (
    assert_assignment_respects_role_quota,
    sync_team_composition_status,
)
from fantasy_teams.ledger import apply_ledger_movement, find_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_teams.ownership import sync_ownership_on_assign
from leagues.models.league import League


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
) -> FantasyRosterSlot | None:
    account = find_account_for_team(session, team.id, for_update=True)
    if account is None or account.balance < amount_credits:
        return None

    try:
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
) -> FantasyRosterSlot | None:
    """Assign an auction-won athlete to the team's first free slot.

    Returns the updated slot on success, or ``None`` when the assignment
    cannot be honored (no free slot, insufficient credits, or role quota
    exceeded) — those are legitimate "lost bid" outcomes per FR-AST-01
    ("segnala le rose ancora incomplete"), not fatal errors.
    """
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
