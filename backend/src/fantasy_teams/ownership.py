"""Roster ownership intervals and turn snapshots (EP05-06)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from database.enums import RosterOwnershipSource
from fantasy_teams.models import (
    FantasyRosterSlot,
    FantasyTeam,
    RosterOwnershipInterval,
    RosterTurnSnapshot,
    RosterTurnSnapshotEntry,
)
from leagues.models.league_calendar import LeagueCalendar
from sports_data.listone.generate import get_role_assignment
from sports_data.listone.overrides import effective_role_for_athlete, get_active_override


@dataclass(frozen=True, slots=True)
class OwnershipAssignResult:
    closed: RosterOwnershipInterval | None
    opened: RosterOwnershipInterval | None
    updated: RosterOwnershipInterval | None


def validate_round_number(round_number: int) -> int:
    if round_number < 1:
        raise ValidationAuthError(
            "Il numero di turno deve essere almeno 1.",
            code="invalid_round_number",
        )
    return round_number


def validate_round_against_calendar(
    session: Session,
    *,
    league_id: UUID,
    round_number: int,
) -> None:
    calendar = session.scalar(select(LeagueCalendar).where(LeagueCalendar.league_id == league_id))
    if calendar is not None and round_number > calendar.round_count:
        raise ValidationAuthError(
            f"Il turno {round_number} supera i {calendar.round_count} turni del calendario.",
            code="round_number_out_of_range",
        )


def parse_as_of(value: str | None) -> datetime:
    if value is None or not value.strip():
        return datetime.now(UTC)
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationAuthError(
            "Timestamp as-of non valido (usa ISO-8601 UTC).",
            code="invalid_as_of",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def find_active_interval_for_slot(
    session: Session,
    *,
    fantasy_team_id: UUID,
    slot_index: int,
    for_update: bool = False,
) -> RosterOwnershipInterval | None:
    stmt = select(RosterOwnershipInterval).where(
        RosterOwnershipInterval.fantasy_team_id == fantasy_team_id,
        RosterOwnershipInterval.slot_index == slot_index,
        RosterOwnershipInterval.released_at.is_(None),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def find_active_interval_for_athlete(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
    for_update: bool = False,
) -> RosterOwnershipInterval | None:
    stmt = select(RosterOwnershipInterval).where(
        RosterOwnershipInterval.league_id == league_id,
        RosterOwnershipInterval.athlete_id == athlete_id,
        RosterOwnershipInterval.released_at.is_(None),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def close_ownership_interval(
    session: Session,
    interval: RosterOwnershipInterval,
    *,
    released_at: datetime | None = None,
) -> RosterOwnershipInterval:
    if interval.released_at is not None:
        return interval
    moment = released_at or datetime.now(UTC)
    if moment < interval.acquired_at:
        moment = interval.acquired_at
    interval.released_at = moment
    session.flush()
    return interval


def open_ownership_interval(
    session: Session,
    *,
    league_id: UUID,
    fantasy_team_id: UUID,
    athlete_id: UUID,
    slot_index: int,
    purchase_credits: int,
    source: RosterOwnershipSource,
    acquired_at: datetime | None = None,
) -> RosterOwnershipInterval:
    interval = RosterOwnershipInterval(
        league_id=league_id,
        fantasy_team_id=fantasy_team_id,
        athlete_id=athlete_id,
        slot_index=slot_index,
        purchase_credits=purchase_credits,
        acquired_at=acquired_at or datetime.now(UTC),
        released_at=None,
        source=source,
    )
    session.add(interval)
    session.flush()
    return interval


def sync_ownership_on_assign(
    session: Session,
    *,
    league_id: UUID,
    fantasy_team_id: UUID,
    slot_index: int,
    athlete_id: UUID,
    purchase_credits: int,
    source: RosterOwnershipSource,
    previous_athlete_id: UUID | None,
) -> OwnershipAssignResult:
    """Close previous interval when needed and open/update the active one."""
    now = datetime.now(UTC)
    active = find_active_interval_for_slot(
        session,
        fantasy_team_id=fantasy_team_id,
        slot_index=slot_index,
        for_update=True,
    )

    if active is not None and active.athlete_id == athlete_id and previous_athlete_id == athlete_id:
        if active.purchase_credits != purchase_credits:
            active.purchase_credits = purchase_credits
            session.flush()
        return OwnershipAssignResult(closed=None, opened=None, updated=active)

    closed: RosterOwnershipInterval | None = None
    if active is not None:
        closed = close_ownership_interval(session, active, released_at=now)

    opened = open_ownership_interval(
        session,
        league_id=league_id,
        fantasy_team_id=fantasy_team_id,
        athlete_id=athlete_id,
        slot_index=slot_index,
        purchase_credits=purchase_credits,
        source=source,
        acquired_at=now,
    )
    return OwnershipAssignResult(closed=closed, opened=opened, updated=None)


def sync_ownership_on_release(
    session: Session,
    *,
    fantasy_team_id: UUID,
    slot_index: int,
) -> RosterOwnershipInterval | None:
    active = find_active_interval_for_slot(
        session,
        fantasy_team_id=fantasy_team_id,
        slot_index=slot_index,
        for_update=True,
    )
    if active is None:
        return None
    return close_ownership_interval(session, active)


def list_ownership_intervals(
    session: Session,
    *,
    fantasy_team_id: UUID,
    active_only: bool = False,
) -> list[RosterOwnershipInterval]:
    stmt = (
        select(RosterOwnershipInterval)
        .options(selectinload(RosterOwnershipInterval.athlete))
        .where(RosterOwnershipInterval.fantasy_team_id == fantasy_team_id)
        .order_by(
            RosterOwnershipInterval.acquired_at.desc(),
            RosterOwnershipInterval.slot_index.asc(),
        )
    )
    if active_only:
        stmt = stmt.where(RosterOwnershipInterval.released_at.is_(None))
    return list(session.scalars(stmt).all())


def intervals_as_of(
    session: Session,
    *,
    fantasy_team_id: UUID,
    at: datetime,
) -> list[RosterOwnershipInterval]:
    stmt = (
        select(RosterOwnershipInterval)
        .options(selectinload(RosterOwnershipInterval.athlete))
        .where(
            RosterOwnershipInterval.fantasy_team_id == fantasy_team_id,
            RosterOwnershipInterval.acquired_at <= at,
            or_(
                RosterOwnershipInterval.released_at.is_(None),
                RosterOwnershipInterval.released_at > at,
            ),
        )
        .order_by(RosterOwnershipInterval.slot_index.asc())
    )
    return list(session.scalars(stmt).all())


def resolve_slot_role(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
    season_year: int,
) -> str | None:
    assignment = get_role_assignment(
        session,
        athlete_id=athlete_id,
        season_year=season_year,
    )
    if assignment is None:
        return None
    override = get_active_override(
        session,
        league_id=league_id,
        athlete_id=athlete_id,
    )
    return effective_role_for_athlete(
        official_role=assignment.role,
        override=override,
        current_round=0,
    ).value


def find_snapshot(
    session: Session,
    *,
    league_id: UUID,
    round_number: int,
    with_entries: bool = False,
) -> RosterTurnSnapshot | None:
    stmt = select(RosterTurnSnapshot).where(
        RosterTurnSnapshot.league_id == league_id,
        RosterTurnSnapshot.round_number == round_number,
    )
    if with_entries:
        stmt = stmt.options(
            selectinload(RosterTurnSnapshot.entries).selectinload(RosterTurnSnapshotEntry.athlete),
            selectinload(RosterTurnSnapshot.entries).selectinload(
                RosterTurnSnapshotEntry.fantasy_team
            ),
        )
    return session.scalar(stmt)


def list_snapshots(
    session: Session,
    *,
    league_id: UUID,
) -> list[RosterTurnSnapshot]:
    return list(
        session.scalars(
            select(RosterTurnSnapshot)
            .where(RosterTurnSnapshot.league_id == league_id)
            .order_by(RosterTurnSnapshot.round_number.asc())
        ).all()
    )


def create_turn_snapshot(
    session: Session,
    *,
    league_id: UUID,
    round_number: int,
    season_year: int,
    actor_id: UUID | None,
) -> tuple[RosterTurnSnapshot, bool]:
    """Create an immutable snapshot; returns (snapshot, created)."""
    validate_round_number(round_number)
    validate_round_against_calendar(session, league_id=league_id, round_number=round_number)

    existing = find_snapshot(
        session, league_id=league_id, round_number=round_number, with_entries=True
    )
    if existing is not None:
        return existing, False

    teams = list(
        session.scalars(
            select(FantasyTeam)
            .options(selectinload(FantasyTeam.slots))
            .where(FantasyTeam.league_id == league_id)
            .order_by(FantasyTeam.created_at.asc())
        ).all()
    )
    now = datetime.now(UTC)
    snapshot = RosterTurnSnapshot(
        league_id=league_id,
        round_number=round_number,
        captured_at=now,
        actor_id=actor_id,
        entry_count=0,
    )
    session.add(snapshot)
    session.flush()

    entries: list[RosterTurnSnapshotEntry] = []
    for team in teams:
        for slot in sorted(team.slots, key=lambda row: row.slot_index):
            if slot.athlete_id is None:
                continue
            role = resolve_slot_role(
                session,
                league_id=league_id,
                athlete_id=slot.athlete_id,
                season_year=season_year,
            )
            entries.append(
                RosterTurnSnapshotEntry(
                    snapshot_id=snapshot.id,
                    fantasy_team_id=team.id,
                    slot_index=slot.slot_index,
                    athlete_id=slot.athlete_id,
                    purchase_credits=slot.purchase_credits or 0,
                    role=role,
                )
            )
    session.add_all(entries)
    snapshot.entry_count = len(entries)
    session.flush()
    return (
        find_snapshot(session, league_id=league_id, round_number=round_number, with_entries=True)
        or snapshot,
        True,
    )


def count_active_intervals_for_athlete(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
) -> int:
    return len(
        session.scalars(
            select(RosterOwnershipInterval).where(
                and_(
                    RosterOwnershipInterval.league_id == league_id,
                    RosterOwnershipInterval.athlete_id == athlete_id,
                    RosterOwnershipInterval.released_at.is_(None),
                )
            )
        ).all()
    )


def filled_slots_as_of_count(intervals: list[RosterOwnershipInterval]) -> int:
    return len(intervals)


# Re-export for callers that need current slots during snapshot building.
__all__ = [
    "FantasyRosterSlot",
    "close_ownership_interval",
    "count_active_intervals_for_athlete",
    "create_turn_snapshot",
    "filled_slots_as_of_count",
    "find_active_interval_for_athlete",
    "find_active_interval_for_slot",
    "find_snapshot",
    "intervals_as_of",
    "list_ownership_intervals",
    "list_snapshots",
    "open_ownership_interval",
    "parse_as_of",
    "resolve_slot_role",
    "sync_ownership_on_assign",
    "sync_ownership_on_release",
    "validate_round_against_calendar",
    "validate_round_number",
]
