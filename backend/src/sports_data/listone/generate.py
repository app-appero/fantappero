"""Idempotent generation of the official listone with P–D–C–A roles (EP04-04)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import database.models  # noqa: F401 — register ORM mappers
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import SportSeason
from sports_data.listone.mapping import MAPPING_VERSION, map_provider_position_to_role
from sports_data.listone.models import RoleAssignment
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.roster.models import Athlete, SquadMembership

logger = get_logger(__name__)

LISTONE_GENERATE_RUNS_TOTAL = "listone_generate_runs_total"
LISTONE_GENERATE_ENTITIES_TOTAL = "listone_generate_entities_total"
LISTONE_GENERATE_DURATION_SECONDS = "listone_generate_duration_seconds"
LISTONE_UNMAPPED_POSITIONS_TOTAL = "listone_unmapped_positions_total"

UpsertResult = str  # created | updated | unchanged | skipped_unmapped | deactivated


@dataclass
class ListoneGenerateCounters:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_unmapped: int = 0
    deactivated: int = 0

    def incr(self, result: UpsertResult) -> None:
        if hasattr(self, result):
            setattr(self, result, getattr(self, result) + 1)
        get_metrics().incr(
            LISTONE_GENERATE_ENTITIES_TOTAL,
            labels={"provider": PROVIDER_NAME, "result": result},
        )


@dataclass
class ListoneGenerateResult:
    season_year: int
    mapping_version: str
    counters: ListoneGenerateCounters = field(default_factory=ListoneGenerateCounters)


def _touch_updated_at(row: Any) -> None:
    if hasattr(row, "updated_at"):
        row.updated_at = datetime.now(UTC)


def _active_memberships_for_season(session: Session, season_year: int) -> list[SquadMembership]:
    stmt = (
        select(SquadMembership)
        .join(SportSeason, SquadMembership.sport_season_id == SportSeason.id)
        .where(
            SportSeason.year == season_year,
            SquadMembership.is_active.is_(True),
        )
        .options(selectinload(SquadMembership.athlete))
        .order_by(SquadMembership.updated_at.desc())
    )
    return list(session.execute(stmt).scalars().all())


def _pick_membership_per_athlete(
    memberships: list[SquadMembership],
) -> dict[UUID, SquadMembership]:
    """One active membership per athlete (most recently updated wins)."""
    chosen: dict[UUID, SquadMembership] = {}
    for membership in memberships:
        if membership.athlete_id not in chosen:
            chosen[membership.athlete_id] = membership
    return chosen


def _upsert_assignment(
    session: Session,
    *,
    athlete_id: UUID,
    season_year: int,
    membership: SquadMembership,
    counters: ListoneGenerateCounters,
) -> RoleAssignment | None:
    role = map_provider_position_to_role(membership.provider_position_raw)
    if role is None:
        counters.incr("skipped_unmapped")
        get_metrics().incr(
            LISTONE_UNMAPPED_POSITIONS_TOTAL,
            labels={"provider": PROVIDER_NAME},
        )
        logger.warning(
            "listone_position_unmapped",
            extra={
                "athlete_id": str(athlete_id),
                "season_year": season_year,
                "provider_position_raw": membership.provider_position_raw,
            },
        )
        return None

    row = session.execute(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == athlete_id,
            RoleAssignment.season_year == season_year,
        )
    ).scalar_one_or_none()

    if row is None:
        row = RoleAssignment(
            athlete_id=athlete_id,
            season_year=season_year,
            role=role,
            provider_position_raw=membership.provider_position_raw,
            mapping_version=MAPPING_VERSION,
            squad_membership_id=membership.id,
            club_id=membership.club_id,
        )
        session.add(row)
        counters.incr("created")
        return row

    changed = (
        row.role != role
        or row.provider_position_raw != membership.provider_position_raw
        or row.mapping_version != MAPPING_VERSION
        or row.squad_membership_id != membership.id
        or row.club_id != membership.club_id
    )
    if not changed:
        counters.incr("unchanged")
        return row

    row.role = role
    row.provider_position_raw = membership.provider_position_raw
    row.mapping_version = MAPPING_VERSION
    row.squad_membership_id = membership.id
    row.club_id = membership.club_id
    _touch_updated_at(row)
    counters.incr("updated")
    return row


def generate_official_listone(session: Session, *, season_year: int) -> ListoneGenerateResult:
    """Build/refresh official role assignments from active squad memberships."""
    counters = ListoneGenerateCounters()
    metrics = get_metrics()
    status = "ok"
    with Timer(
        metrics,
        LISTONE_GENERATE_DURATION_SECONDS,
        labels={"provider": PROVIDER_NAME},
    ):
        try:
            memberships = _active_memberships_for_season(session, season_year)
            by_athlete = _pick_membership_per_athlete(memberships)
            kept_athlete_ids = set(by_athlete.keys())

            for athlete_id, membership in by_athlete.items():
                _upsert_assignment(
                    session,
                    athlete_id=athlete_id,
                    season_year=season_year,
                    membership=membership,
                    counters=counters,
                )

            stale_stmt = select(RoleAssignment).where(RoleAssignment.season_year == season_year)
            if kept_athlete_ids:
                stale_stmt = stale_stmt.where(RoleAssignment.athlete_id.not_in(kept_athlete_ids))
            stale = session.execute(stale_stmt).scalars().all()
            for row in stale:
                session.delete(row)
                counters.incr("deactivated")

            session.flush()
            logger.info(
                "listone_generate_ok",
                extra={
                    "season_year": season_year,
                    "mapping_version": MAPPING_VERSION,
                    "created": counters.created,
                    "updated": counters.updated,
                    "unchanged": counters.unchanged,
                    "skipped_unmapped": counters.skipped_unmapped,
                    "deactivated": counters.deactivated,
                },
            )
        except Exception:
            status = "error"
            logger.exception(
                "listone_generate_failed",
                extra={"season_year": season_year},
            )
            raise
        finally:
            metrics.incr(
                LISTONE_GENERATE_RUNS_TOTAL,
                labels={"provider": PROVIDER_NAME, "status": status},
            )

    return ListoneGenerateResult(
        season_year=season_year,
        mapping_version=MAPPING_VERSION,
        counters=counters,
    )


def get_role_assignment(
    session: Session,
    *,
    athlete_id: UUID,
    season_year: int,
) -> RoleAssignment | None:
    return session.execute(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == athlete_id,
            RoleAssignment.season_year == season_year,
        )
    ).scalar_one_or_none()


def list_role_assignments(
    session: Session,
    *,
    season_year: int,
    athlete_ids: list[UUID] | None = None,
) -> list[RoleAssignment]:
    stmt = select(RoleAssignment).where(RoleAssignment.season_year == season_year)
    if athlete_ids is not None:
        if not athlete_ids:
            return []
        stmt = stmt.where(RoleAssignment.athlete_id.in_(athlete_ids))
    stmt = stmt.join(Athlete).order_by(Athlete.canonical_name.asc())
    return list(session.execute(stmt).scalars().all())
