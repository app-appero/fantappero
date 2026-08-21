"""Helpers to create fantasy teams atomically (EP05-01/02)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fantasy_teams.ledger import ensure_credit_account_for_team
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules


def resolve_roster_size(session: Session, league_id: UUID) -> int:
    rules = session.scalar(select(LeagueRules).where(LeagueRules.league_id == league_id))
    if rules is None:
        return 35
    return rules.roster_size


def find_team_for_membership(
    session: Session,
    membership_id: UUID,
    *,
    with_slots: bool = False,
) -> FantasyTeam | None:
    stmt = select(FantasyTeam).where(FantasyTeam.membership_id == membership_id)
    if with_slots:
        stmt = stmt.options(
            selectinload(FantasyTeam.slots).selectinload(FantasyRosterSlot.athlete),
            selectinload(FantasyTeam.membership).selectinload(LeagueMembership.user),
        )
    else:
        stmt = stmt.options(
            selectinload(FantasyTeam.membership).selectinload(LeagueMembership.user),
        )
    return session.scalar(stmt)


def find_team_by_id(
    session: Session,
    *,
    league_id: UUID,
    team_id: UUID,
    with_slots: bool = False,
) -> FantasyTeam | None:
    stmt = select(FantasyTeam).where(
        FantasyTeam.id == team_id,
        FantasyTeam.league_id == league_id,
    )
    if with_slots:
        stmt = stmt.options(
            selectinload(FantasyTeam.slots).selectinload(FantasyRosterSlot.athlete),
            selectinload(FantasyTeam.membership).selectinload(LeagueMembership.user),
        )
    else:
        stmt = stmt.options(
            selectinload(FantasyTeam.membership).selectinload(LeagueMembership.user),
        )
    return session.scalar(stmt)


def create_team_with_empty_slots(
    session: Session,
    *,
    membership: LeagueMembership,
    name: str,
    roster_size: int,
    actor_id: UUID | None = None,
) -> FantasyTeam:
    """Insert a fantasy team, empty slots and credit account. Caller owns the transaction."""
    team = FantasyTeam(
        league_id=membership.league_id,
        membership_id=membership.id,
        name=name[:120],
    )
    session.add(team)
    session.flush()
    for slot_index in range(roster_size):
        session.add(
            FantasyRosterSlot(
                fantasy_team_id=team.id,
                league_id=membership.league_id,
                slot_index=slot_index,
                athlete_id=None,
            )
        )
    session.flush()
    ensure_credit_account_for_team(session, team, actor_id=actor_id)
    return team


def ensure_team_for_membership(
    session: Session,
    membership: LeagueMembership,
    *,
    name: str,
    roster_size: int | None = None,
    actor_id: UUID | None = None,
) -> tuple[FantasyTeam, bool]:
    """Idempotently ensure a fantasy team exists for the membership.

    Returns ``(team, created)``. Existing teams also get a credit account if missing.
    """
    existing = find_team_for_membership(session, membership.id)
    if existing is not None:
        ensure_credit_account_for_team(session, existing, actor_id=actor_id)
        return existing, False
    size = (
        roster_size
        if roster_size is not None
        else resolve_roster_size(session, membership.league_id)
    )
    team = create_team_with_empty_slots(
        session,
        membership=membership,
        name=name,
        roster_size=size,
        actor_id=actor_id,
    )
    return team, True
