"""Idempotent generation of the official listone with P–D–C–A roles (EP04-04)."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

import database.models  # noqa: F401 — register ORM mappers
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import CompetitionSeasonClub, SportSeason
from sports_data.listone.mapping import MAPPING_VERSION, map_provider_position_to_role
from sports_data.listone.models import RoleAssignment
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.roster.models import Athlete, SquadMembership, Transfer

logger = get_logger(__name__)

LISTONE_GENERATE_RUNS_TOTAL = "listone_generate_runs_total"
LISTONE_GENERATE_ENTITIES_TOTAL = "listone_generate_entities_total"
LISTONE_GENERATE_DURATION_SECONDS = "listone_generate_duration_seconds"
LISTONE_UNMAPPED_POSITIONS_TOTAL = "listone_unmapped_positions_total"
LISTONE_ROLE_CHANGES_SKIPPED_TOTAL = "listone_role_changes_skipped_total"

UpsertResult = str  # created | updated | unchanged | skipped_unmapped | deactivated


@dataclass
class ListoneGenerateCounters:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_unmapped: int = 0
    deactivated: int = 0
    #: Calciatori già nel listone per cui il fornitore indica oggi un altro ruolo: il ruolo
    #: ufficiale resta quello (congelato per la stagione), la differenza si conta qui.
    role_changes_skipped: int = 0

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
    #: Calciatori con assegnazione creata, cambiata (ruolo o club) o tolta: il loro ruolo
    #: effettivo può essere cambiato e le rose che li contengono vanno ricalcolate
    #: (`fantasy_teams.composition_service.resync_team_compositions`).
    affected_athlete_ids: set[UUID] = field(default_factory=set)


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


def latest_transfer_destinations(
    session: Session,
    athlete_ids: Collection[UUID],
) -> dict[UUID, UUID]:
    """Club di arrivo dell'ultimo trasferimento di ogni calciatore (se il club è censito).

    È il club attuale secondo la storia dei trasferimenti: chi è rientrato dal prestito
    («Back from Loan») è tornato al club che l'aveva prestato, chi è stato ceduto è al club
    che l'ha comprato. Un ultimo trasferimento verso un club non censito non dà preferenze.
    """
    ids = list(dict.fromkeys(athlete_ids))
    if not ids:
        return {}
    destinations: dict[UUID, UUID] = {}
    for start in range(0, len(ids), 1000):
        chunk = ids[start : start + 1000]
        rows = session.execute(
            select(Transfer.athlete_id, Transfer.to_club_id)
            .where(Transfer.athlete_id.in_(chunk))
            .distinct(Transfer.athlete_id)
            .order_by(
                Transfer.athlete_id,
                Transfer.transfer_date.desc(),
                Transfer.created_at.desc(),
            )
        ).all()
        for athlete_id, to_club_id in rows:
            if to_club_id is not None:
                destinations[athlete_id] = to_club_id
    return destinations


def membership_preference(
    *,
    club_id: UUID,
    source: str | None,
    provider_position_raw: str | None,
    current_club_id: UUID | None,
) -> tuple[bool, bool, bool]:
    """Ordine di preferenza fra più membership attive dello stesso calciatore (più alto vince).

    Prima il club attuale (arrivo dell'ultimo trasferimento), poi la rosa attuale del
    fornitore (``/players/squads``, la fonte scritta per ultima nella sync), poi una
    posizione che dà un ruolo. Una membership riattivata o appena toccata da una sync non
    vince più solo perché è la più recente: con la correzione dei prestiti del 21/11 un
    calciatore può avere attiva anche quella del club che ha lasciato, che il fornitore
    elenca ancora, con un'altra posizione.
    """
    return (
        current_club_id is not None and club_id == current_club_id,
        source == "squads",
        map_provider_position_to_role(provider_position_raw) is not None,
    )


def _pick_membership_per_athlete(
    memberships: list[SquadMembership],
    current_clubs: Mapping[UUID, UUID] | None = None,
) -> dict[UUID, SquadMembership]:
    """Una membership attiva per calciatore.

    Con più membership attive vince quella del club attuale (`membership_preference`); a
    parità la più recente (``memberships`` arriva in ordine di ``updated_at`` decrescente).
    """
    clubs = current_clubs or {}
    chosen: dict[UUID, SquadMembership] = {}
    chosen_rank: dict[UUID, tuple[bool, bool, bool]] = {}
    for membership in memberships:
        rank = membership_preference(
            club_id=membership.club_id,
            source=membership.source,
            provider_position_raw=membership.provider_position_raw,
            current_club_id=clubs.get(membership.athlete_id),
        )
        best = chosen_rank.get(membership.athlete_id)
        if best is None or rank > best:
            chosen[membership.athlete_id] = membership
            chosen_rank[membership.athlete_id] = rank
    return chosen


def pick_active_memberships(session: Session, season_year: int) -> dict[UUID, SquadMembership]:
    """La membership che vale per il listone, per ogni calciatore con membership attiva."""
    memberships = _active_memberships_for_season(session, season_year)
    counts: dict[UUID, int] = {}
    for membership in memberships:
        counts[membership.athlete_id] = counts.get(membership.athlete_id, 0) + 1
    multi = [athlete_id for athlete_id, count in counts.items() if count > 1]
    return _pick_membership_per_athlete(
        memberships,
        latest_transfer_destinations(session, multi),
    )


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

    # Ruoli congelati per la stagione (Rosario 22/11): un calciatore già nel listone tiene il
    # suo ruolo ufficiale anche se il fornitore oggi indica un'altra posizione, perché un
    # cambio silenzioso manda fuori quota rose già valide. Club e membership si aggiornano.
    # Il ruolo cambia solo con un'azione esplicita: override di lega, «Aggiorna anche i
    # ruoli dal fornitore» o «Ripristina i ruoli» dal pannello operatore.
    position_raw = membership.provider_position_raw
    if row.role != role:
        counters.role_changes_skipped += 1
        get_metrics().incr(
            LISTONE_ROLE_CHANGES_SKIPPED_TOTAL,
            labels={"provider": PROVIDER_NAME},
        )
        logger.info(
            "listone_role_change_skipped",
            extra={
                "athlete_id": str(athlete_id),
                "season_year": season_year,
                "role": row.role.value,
                "provider_role": role.value,
                "provider_position_raw": membership.provider_position_raw,
            },
        )
        # La posizione salvata resta quella da cui viene il ruolo ufficiale.
        position_raw = row.provider_position_raw

    changed = (
        row.provider_position_raw != position_raw
        or row.mapping_version != MAPPING_VERSION
        or row.squad_membership_id != membership.id
        or row.club_id != membership.club_id
    )
    if not changed:
        counters.incr("unchanged")
        return row

    row.provider_position_raw = position_raw
    row.mapping_version = MAPPING_VERSION
    row.squad_membership_id = membership.id
    row.club_id = membership.club_id
    _touch_updated_at(row)
    counters.incr("updated")
    return row


def generate_official_listone(
    session: Session,
    *,
    season_year: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> ListoneGenerateResult:
    """Build/refresh official role assignments from active squad memberships.

    New athletes get the role mapped from their provider position; athletes already in the
    season listone keep their role (frozen, see ``_upsert_assignment``), while club,
    membership and position metadata follow the provider.
    """
    counters = ListoneGenerateCounters()
    affected: set[UUID] = set()
    metrics = get_metrics()
    status = "ok"
    with Timer(
        metrics,
        LISTONE_GENERATE_DURATION_SECONDS,
        labels={"provider": PROVIDER_NAME},
    ):
        try:
            by_athlete = pick_active_memberships(session, season_year)
            kept_athlete_ids = set(by_athlete.keys())
            assignments = list(by_athlete.items())
            assignment_total = len(assignments)

            for index, (athlete_id, membership) in enumerate(assignments, start=1):
                before = (counters.created, counters.updated)
                _upsert_assignment(
                    session,
                    athlete_id=athlete_id,
                    season_year=season_year,
                    membership=membership,
                    counters=counters,
                )
                if (counters.created, counters.updated) != before:
                    affected.add(athlete_id)
                if on_progress is not None and (index == assignment_total or index % 100 == 0):
                    on_progress(index, assignment_total)

            stale_stmt = select(RoleAssignment).where(RoleAssignment.season_year == season_year)
            if kept_athlete_ids:
                stale_stmt = stale_stmt.where(RoleAssignment.athlete_id.not_in(kept_athlete_ids))
            stale = session.execute(stale_stmt).scalars().all()
            for row in stale:
                affected.add(row.athlete_id)
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
                    "role_changes_skipped": counters.role_changes_skipped,
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
        affected_athlete_ids=affected,
    )


def _competition_filter_clause(*, season_year: int, competition_ids: set[UUID]):
    """Match role_assignments whose club plays in one of the given competitions.

    Rows with ``club_id IS NULL`` are never excluded — in production
    ``generate_official_listone`` always sets ``club_id``, but treating a
    missing club as "out of competition" would silently hide data-quality
    gaps rather than surface a real cross-competition mismatch.
    """
    club_ids_in_competitions = (
        select(CompetitionSeasonClub.club_id)
        .join(SportSeason, SportSeason.id == CompetitionSeasonClub.sport_season_id)
        .where(
            SportSeason.year == season_year,
            SportSeason.competition_id.in_(competition_ids),
        )
    )
    return or_(
        RoleAssignment.club_id.is_(None),
        RoleAssignment.club_id.in_(club_ids_in_competitions),
    )


def get_role_assignment(
    session: Session,
    *,
    athlete_id: UUID,
    season_year: int,
    competition_ids: set[UUID] | None = None,
) -> RoleAssignment | None:
    stmt = select(RoleAssignment).where(
        RoleAssignment.athlete_id == athlete_id,
        RoleAssignment.season_year == season_year,
    )
    if competition_ids is not None:
        stmt = stmt.where(
            _competition_filter_clause(season_year=season_year, competition_ids=competition_ids)
        )
    return session.execute(stmt).scalar_one_or_none()


def list_role_assignments(
    session: Session,
    *,
    season_year: int,
    athlete_ids: list[UUID] | None = None,
    competition_ids: set[UUID] | None = None,
) -> list[RoleAssignment]:
    stmt = select(RoleAssignment).where(RoleAssignment.season_year == season_year)
    if athlete_ids is not None:
        if not athlete_ids:
            return []
        stmt = stmt.where(RoleAssignment.athlete_id.in_(athlete_ids))
    if competition_ids is not None:
        stmt = stmt.where(
            _competition_filter_clause(season_year=season_year, competition_ids=competition_ids)
        )
    stmt = stmt.join(Athlete).order_by(Athlete.canonical_name.asc())
    return list(session.execute(stmt).scalars().all())
