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

    account = find_account_for_team(session, team.id, for_update=True)
    if account is None or account.balance < amount_credits:
        return None

    try:
        assert_assignment_respects_role_quota(
            session,
            league=league,
            team=team,
            athlete_id=athlete_id,
            slot_index=slot.slot_index,
        )
    except ValidationAuthError:
        return None

    try:
        with session.begin_nested():
            slot.athlete_id = athlete_id
            slot.purchase_credits = amount_credits
            session.flush()
    except IntegrityError:
        return None

    apply_ledger_movement(
        session,
        account,
        amount=-amount_credits,
        reason=CreditLedgerReason.MARKET_AUCTION_WIN,
        transaction_id=transaction_id,
        actor_id=actor_id,
        note="Assegnazione da asta a buste",
    )
    sync_ownership_on_assign(
        session,
        league_id=league.id,
        fantasy_team_id=team.id,
        slot_index=slot.slot_index,
        athlete_id=athlete_id,
        purchase_credits=amount_credits,
        source=RosterOwnershipSource.MARKET,
        previous_athlete_id=None,
    )
    sync_team_composition_status(session, team, league=league)
    return slot
