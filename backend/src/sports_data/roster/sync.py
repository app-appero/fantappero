"""Idempotent sync of athletes, squad memberships and transfers (EP04-03)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from leagues.models.competition import Competition
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import Club, SportSeason
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.constants import MVP_LEAGUE_IDS, PROVIDER_NAME
from sports_data.provider.mapping import (
    map_athletes_from_players,
    map_squad_memberships,
    map_squad_memberships_from_players,
    map_transfers,
)
from sports_data.provider.snapshots import store_provider_snapshot
from sports_data.provider.types import (
    MappedAthlete,
    MappedSquadMembership,
    MappedTransfer,
    ProviderEnvelope,
)
from sports_data.roster.models import Athlete, SquadMembership, Transfer
from sports_data.roster.validators import transfer_requires_admin_review

logger = get_logger(__name__)

ROSTER_SYNC_RUNS_TOTAL = "roster_sync_runs_total"
ROSTER_SYNC_ENTITIES_TOTAL = "roster_sync_entities_total"
ROSTER_SYNC_DURATION_SECONDS = "roster_sync_duration_seconds"

UpsertResult = str  # created | updated | unchanged | deactivated | skipped_missing_club


@dataclass
class RosterSyncCounters:
    athletes_created: int = 0
    athletes_updated: int = 0
    athletes_unchanged: int = 0
    memberships_created: int = 0
    memberships_updated: int = 0
    memberships_unchanged: int = 0
    memberships_deactivated: int = 0
    memberships_skipped_missing_club: int = 0
    transfers_created: int = 0
    transfers_unchanged: int = 0
    transfers_skipped_missing_club: int = 0
    snapshots_stored: int = 0
    snapshots_deduped: int = 0

    def incr_entity(self, entity: str, result: UpsertResult) -> None:
        attr = f"{entity}_{result}"
        if hasattr(self, attr):
            setattr(self, attr, getattr(self, attr) + 1)
        get_metrics().incr(
            ROSTER_SYNC_ENTITIES_TOTAL,
            labels={"provider": PROVIDER_NAME, "entity": entity, "result": result},
        )


@dataclass
class RosterSyncResult:
    counters: RosterSyncCounters = field(default_factory=RosterSyncCounters)


@dataclass(frozen=True)
class SquadBatch:
    """Squad envelope scoped to a competition season and club."""

    envelope: ProviderEnvelope
    club_provider_id: int
    competition_provider_id: int
    season_year: int


@dataclass(frozen=True)
class PlayersBatch:
    """Players envelope scoped to team + season."""

    envelope: ProviderEnvelope
    club_provider_id: int
    season_year: int


def _touch_updated_at(row: Any) -> None:
    if hasattr(row, "updated_at"):
        row.updated_at = datetime.now(UTC)


def _resolve_club(session: Session, provider_id: int | None) -> Club | None:
    if provider_id is None:
        return None
    return session.execute(
        select(Club).where(Club.provider_id == provider_id),
    ).scalar_one_or_none()


def _resolve_sport_season(
    session: Session,
    *,
    competition_provider_id: int,
    season_year: int,
) -> SportSeason | None:
    competition = session.execute(
        select(Competition).where(Competition.provider_id == competition_provider_id),
    ).scalar_one_or_none()
    if competition is None:
        return None
    return session.execute(
        select(SportSeason).where(
            SportSeason.competition_id == competition.id,
            SportSeason.year == season_year,
        ),
    ).scalar_one_or_none()


def upsert_athlete(
    session: Session,
    mapped: MappedAthlete,
    counters: RosterSyncCounters,
) -> Athlete:
    row = session.execute(
        select(Athlete).where(Athlete.provider_id == mapped.provider_id),
    ).scalar_one_or_none()
    if row is None:
        row = Athlete(
            provider_id=mapped.provider_id,
            canonical_name=mapped.canonical_name,
            first_name=mapped.first_name,
            last_name=mapped.last_name,
            nationality=mapped.nationality,
            birth_date=mapped.birth_date,
            height=mapped.height,
            weight=mapped.weight,
            age=mapped.age,
            injured=mapped.injured,
        )
        session.add(row)
        session.flush()
        counters.incr_entity("athletes", "created")
        return row

    fields = {
        "canonical_name": mapped.canonical_name,
        "first_name": mapped.first_name,
        "last_name": mapped.last_name,
        "nationality": mapped.nationality,
        "birth_date": mapped.birth_date,
        "height": mapped.height,
        "weight": mapped.weight,
        "age": mapped.age,
        "injured": mapped.injured,
    }
    changed = False
    for key, value in fields.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        _touch_updated_at(row)
        counters.incr_entity("athletes", "updated")
    else:
        counters.incr_entity("athletes", "unchanged")
    return row


def upsert_athlete_from_membership(
    session: Session,
    mapped: MappedSquadMembership,
    counters: RosterSyncCounters,
) -> Athlete:
    return upsert_athlete(
        session,
        MappedAthlete(
            provider_id=mapped.athlete_provider_id,
            canonical_name=mapped.athlete_name,
            age=mapped.athlete_age,
        ),
        counters,
    )


def _athlete_has_transfer_out(
    session: Session,
    *,
    athlete_id: UUID,
    club_id: UUID,
) -> bool:
    return (
        session.execute(
            select(Transfer.id).where(
                Transfer.athlete_id == athlete_id,
                Transfer.from_club_id == club_id,
            ),
        ).first()
        is not None
    )


def upsert_squad_membership(
    session: Session,
    mapped: MappedSquadMembership,
    counters: RosterSyncCounters,
) -> SquadMembership | None:
    club = _resolve_club(session, mapped.club_provider_id)
    if club is None:
        counters.memberships_skipped_missing_club += 1
        get_metrics().incr(
            ROSTER_SYNC_ENTITIES_TOTAL,
            labels={
                "provider": PROVIDER_NAME,
                "entity": "memberships",
                "result": "skipped_missing_club",
            },
        )
        logger.warning(
            "roster_membership_skipped_missing_club",
            extra={
                "provider": PROVIDER_NAME,
                "club_provider_id": mapped.club_provider_id,
                "athlete_provider_id": mapped.athlete_provider_id,
            },
        )
        return None

    sport_season = _resolve_sport_season(
        session,
        competition_provider_id=mapped.competition_provider_id,
        season_year=mapped.season_year,
    )
    if sport_season is None:
        counters.memberships_skipped_missing_club += 1
        get_metrics().incr(
            ROSTER_SYNC_ENTITIES_TOTAL,
            labels={
                "provider": PROVIDER_NAME,
                "entity": "memberships",
                "result": "skipped_missing_club",
            },
        )
        logger.warning(
            "roster_membership_skipped_missing_season",
            extra={
                "provider": PROVIDER_NAME,
                "competition_provider_id": mapped.competition_provider_id,
                "season_year": mapped.season_year,
                "athlete_provider_id": mapped.athlete_provider_id,
            },
        )
        return None

    athlete = upsert_athlete_from_membership(session, mapped, counters)
    should_be_active = not _athlete_has_transfer_out(
        session,
        athlete_id=athlete.id,
        club_id=club.id,
    )
    row = session.execute(
        select(SquadMembership).where(
            SquadMembership.athlete_id == athlete.id,
            SquadMembership.club_id == club.id,
            SquadMembership.sport_season_id == sport_season.id,
        ),
    ).scalar_one_or_none()

    fields = {
        "shirt_number": mapped.shirt_number,
        "provider_position_raw": mapped.provider_position_raw,
        "is_active": should_be_active,
        "ended_at": None if should_be_active else row.ended_at if row else None,
        "source": mapped.source,
    }
    if row is None:
        row = SquadMembership(
            athlete_id=athlete.id,
            club_id=club.id,
            sport_season_id=sport_season.id,
            **fields,
        )
        session.add(row)
        session.flush()
        counters.incr_entity("memberships", "created")
        return row

    changed = False
    for key, value in fields.items():
        if key == "ended_at" and not should_be_active and row.ended_at is not None:
            continue
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        _touch_updated_at(row)
        counters.incr_entity("memberships", "updated")
    else:
        counters.incr_entity("memberships", "unchanged")
    return row


def _deactivate_membership(
    membership: SquadMembership,
    *,
    ended_at: date,
    counters: RosterSyncCounters,
) -> None:
    if membership.is_active or membership.ended_at != ended_at:
        membership.is_active = False
        membership.ended_at = ended_at
        _touch_updated_at(membership)
        counters.incr_entity("memberships", "deactivated")


def upsert_transfer(
    session: Session,
    mapped: MappedTransfer,
    counters: RosterSyncCounters,
) -> Transfer | None:
    existing = session.execute(
        select(Transfer).where(Transfer.provider_key == mapped.provider_key),
    ).scalar_one_or_none()
    if existing is not None:
        counters.incr_entity("transfers", "unchanged")
        return existing

    athlete = upsert_athlete(
        session,
        MappedAthlete(
            provider_id=mapped.athlete_provider_id,
            canonical_name=mapped.athlete_name or f"Calciatore {mapped.athlete_provider_id}",
        ),
        counters,
    )
    from_club = _resolve_club(session, mapped.from_club_provider_id)
    to_club = _resolve_club(session, mapped.to_club_provider_id)
    if mapped.from_club_provider_id is not None and from_club is None:
        counters.transfers_skipped_missing_club += 1
        get_metrics().incr(
            ROSTER_SYNC_ENTITIES_TOTAL,
            labels={
                "provider": PROVIDER_NAME,
                "entity": "transfers",
                "result": "skipped_missing_club",
            },
        )
        logger.warning(
            "roster_transfer_skipped_missing_from_club",
            extra={
                "provider": PROVIDER_NAME,
                "club_provider_id": mapped.from_club_provider_id,
                "athlete_provider_id": mapped.athlete_provider_id,
            },
        )
        return None
    if mapped.to_club_provider_id is not None and to_club is None:
        counters.transfers_skipped_missing_club += 1
        get_metrics().incr(
            ROSTER_SYNC_ENTITIES_TOTAL,
            labels={
                "provider": PROVIDER_NAME,
                "entity": "transfers",
                "result": "skipped_missing_club",
            },
        )
        logger.warning(
            "roster_transfer_skipped_missing_to_club",
            extra={
                "provider": PROVIDER_NAME,
                "club_provider_id": mapped.to_club_provider_id,
                "athlete_provider_id": mapped.athlete_provider_id,
            },
        )
        return None

    row = Transfer(
        athlete_id=athlete.id,
        transfer_date=mapped.transfer_date,
        from_club_id=from_club.id if from_club else None,
        to_club_id=to_club.id if to_club else None,
        transfer_type=mapped.transfer_type,
        requires_admin_review=transfer_requires_admin_review(mapped.transfer_type),
        provider_key=mapped.provider_key,
    )
    session.add(row)
    session.flush()
    counters.incr_entity("transfers", "created")

    _apply_transfer_membership_effects(
        session,
        athlete_id=athlete.id,
        mapped=mapped,
        from_club_id=from_club.id if from_club else None,
        to_club_id=to_club.id if to_club else None,
        counters=counters,
    )
    return row


def _apply_transfer_membership_effects(
    session: Session,
    *,
    athlete_id: UUID,
    mapped: MappedTransfer,
    from_club_id: UUID | None,
    to_club_id: UUID | None,
    counters: RosterSyncCounters,
) -> None:
    """Close origin membership and open destination without deleting history."""
    if from_club_id is not None:
        active_from = session.scalars(
            select(SquadMembership).where(
                SquadMembership.athlete_id == athlete_id,
                SquadMembership.club_id == from_club_id,
                SquadMembership.is_active.is_(True),
            ),
        ).all()
        for membership in active_from:
            _deactivate_membership(
                membership,
                ended_at=mapped.transfer_date,
                counters=counters,
            )

    if to_club_id is not None and mapped.to_club_provider_id is not None:
        from sports_data.catalog.models import CompetitionSeasonClub

        season_links = session.scalars(
            select(CompetitionSeasonClub)
            .join(SportSeason, CompetitionSeasonClub.sport_season_id == SportSeason.id)
            .where(
                CompetitionSeasonClub.club_id == to_club_id,
                SportSeason.is_current.is_(True),
            ),
        ).all()
        for link in season_links:
            sport_season = session.get(SportSeason, link.sport_season_id)
            if sport_season is None:
                continue
            competition = session.get(Competition, sport_season.competition_id)
            if competition is None or competition.provider_id not in MVP_LEAGUE_IDS:
                continue
            membership_mapped = MappedSquadMembership(
                athlete_provider_id=mapped.athlete_provider_id,
                athlete_name=mapped.athlete_name,
                club_provider_id=mapped.to_club_provider_id,
                competition_provider_id=competition.provider_id,
                season_year=sport_season.year,
                source="transfers",
            )
            upsert_squad_membership(session, membership_mapped, counters)
            break


def _maybe_store_snapshot(
    session: Session,
    envelope: ProviderEnvelope,
    counters: RosterSyncCounters,
    *,
    store_snapshots: bool,
) -> None:
    if not store_snapshots:
        return
    _, created = store_provider_snapshot(session, envelope)
    if created:
        counters.snapshots_stored += 1
    else:
        counters.snapshots_deduped += 1


def sync_squads_for_club(
    session: Session,
    envelope: ProviderEnvelope,
    *,
    club_provider_id: int,
    competition_provider_id: int,
    season_year: int,
    store_snapshots: bool = True,
    counters: RosterSyncCounters | None = None,
) -> RosterSyncResult:
    """Upsert squad memberships from a ``/players/squads`` envelope."""
    result = RosterSyncResult(counters=counters or RosterSyncCounters())
    _maybe_store_snapshot(session, envelope, result.counters, store_snapshots=store_snapshots)

    for mapped in map_squad_memberships(
        envelope,
        competition_provider_id=competition_provider_id,
        season_year=season_year,
    ):
        if mapped.club_provider_id != club_provider_id:
            continue
        upsert_squad_membership(session, mapped, result.counters)

    logger.info(
        "roster_squads_synced",
        extra={
            "provider": PROVIDER_NAME,
            "club_provider_id": club_provider_id,
            "competition_provider_id": competition_provider_id,
            "season_year": season_year,
            "memberships_created": result.counters.memberships_created,
        },
    )
    return result


def sync_players_for_club(
    session: Session,
    envelope: ProviderEnvelope,
    *,
    club_provider_id: int,
    season_year: int,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
    counters: RosterSyncCounters | None = None,
) -> RosterSyncResult:
    """Upsert athletes and memberships from ``/players?team&season``."""
    result = RosterSyncResult(counters=counters or RosterSyncCounters())
    allowed = frozenset(league_ids)
    _maybe_store_snapshot(session, envelope, result.counters, store_snapshots=store_snapshots)

    for mapped in map_athletes_from_players(envelope, league_ids=allowed):
        upsert_athlete(session, mapped, result.counters)

    for mapped in map_squad_memberships_from_players(envelope, league_ids=allowed):
        if mapped.club_provider_id != club_provider_id or mapped.season_year != season_year:
            continue
        upsert_squad_membership(session, mapped, result.counters)

    logger.info(
        "roster_players_synced",
        extra={
            "provider": PROVIDER_NAME,
            "club_provider_id": club_provider_id,
            "season_year": season_year,
            "athletes_created": result.counters.athletes_created,
        },
    )
    return result


def sync_transfers(
    session: Session,
    envelope: ProviderEnvelope,
    *,
    store_snapshots: bool = True,
    counters: RosterSyncCounters | None = None,
) -> RosterSyncResult:
    """Upsert transfer history from a ``/transfers`` envelope."""
    result = RosterSyncResult(counters=counters or RosterSyncCounters())
    _maybe_store_snapshot(session, envelope, result.counters, store_snapshots=store_snapshots)

    for mapped in map_transfers(envelope):
        upsert_transfer(session, mapped, result.counters)

    logger.info(
        "roster_transfers_synced",
        extra={
            "provider": PROVIDER_NAME,
            "transfers_created": result.counters.transfers_created,
        },
    )
    return result


def sync_roster(
    session: Session,
    *,
    squad_batches: Sequence[SquadBatch] | None = None,
    players_batches: Sequence[PlayersBatch] | None = None,
    transfers_envelopes: Sequence[ProviderEnvelope] | None = None,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
) -> RosterSyncResult:
    """Atomic roster unit of work: squads, players, then transfers."""
    metrics = get_metrics()
    labels = {"provider": PROVIDER_NAME}
    counters = RosterSyncCounters()
    result = RosterSyncResult(counters=counters)
    try:
        with Timer(metrics, ROSTER_SYNC_DURATION_SECONDS, labels=labels):
            for batch in players_batches or ():
                sync_players_for_club(
                    session,
                    batch.envelope,
                    club_provider_id=batch.club_provider_id,
                    season_year=batch.season_year,
                    league_ids=league_ids,
                    store_snapshots=store_snapshots,
                    counters=counters,
                )
            for envelope in transfers_envelopes or ():
                sync_transfers(
                    session,
                    envelope,
                    store_snapshots=store_snapshots,
                    counters=counters,
                )
            for batch in squad_batches or ():
                if batch.competition_provider_id not in frozenset(league_ids):
                    continue
                sync_squads_for_club(
                    session,
                    batch.envelope,
                    club_provider_id=batch.club_provider_id,
                    competition_provider_id=batch.competition_provider_id,
                    season_year=batch.season_year,
                    store_snapshots=store_snapshots,
                    counters=counters,
                )
        metrics.incr(ROSTER_SYNC_RUNS_TOTAL, labels={**labels, "status": "ok"})
        logger.info(
            "roster_sync_ok",
            extra={
                "provider": PROVIDER_NAME,
                "athletes_created": counters.athletes_created,
                "memberships_created": counters.memberships_created,
                "transfers_created": counters.transfers_created,
            },
        )
    except Exception:
        metrics.incr(ROSTER_SYNC_RUNS_TOTAL, labels={**labels, "status": "error"})
        logger.exception("roster_sync_failed", extra={"provider": PROVIDER_NAME})
        raise
    return result


def sync_mvp_roster_with_client(
    session: Session,
    client: ApiFootballClient,
    *,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
    max_clubs_per_league: int | None = None,
    season_year: int | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> RosterSyncResult:
    """Fetch squads and transfers for MVP clubs already present in catalog.

    When ``season_year`` is set, syncs clubs for that sport season year (preferred for
    listone refresh). Otherwise uses seasons marked ``is_current``.
    """
    from sports_data.catalog.models import CompetitionSeasonClub

    allowed = frozenset(league_ids)
    squad_batches: list[SquadBatch] = []
    players_batches: list[PlayersBatch] = []
    transfer_envelopes: list[ProviderEnvelope] = []

    season_filter = (
        SportSeason.year == season_year
        if season_year is not None
        else SportSeason.is_current.is_(True)
    )
    season_rows = session.scalars(
        select(SportSeason)
        .join(Competition)
        .where(Competition.provider_id.in_(allowed), season_filter),
    ).all()

    work_items: list[tuple[SportSeason, Competition, Club]] = []
    for sport_season in season_rows:
        competition = session.get(Competition, sport_season.competition_id)
        if competition is None:
            continue
        club_query = (
            select(Club)
            .join(CompetitionSeasonClub, CompetitionSeasonClub.club_id == Club.id)
            .where(
                CompetitionSeasonClub.sport_season_id == sport_season.id,
                Club.national.is_(False),
            )
            .order_by(Club.provider_id)
        )
        if max_clubs_per_league is not None:
            club_query = club_query.limit(max_clubs_per_league)
        clubs = session.scalars(club_query).all()
        for club in clubs:
            work_items.append((sport_season, competition, club))

    total = len(work_items)
    if on_progress is not None:
        on_progress(0, max(total, 1), "Avvio sync rose")

    for index, (sport_season, competition, club) in enumerate(work_items, start=1):
        squads = client.get("/players/squads", {"team": club.provider_id})
        squad_batches.append(
            SquadBatch(
                envelope=squads,
                club_provider_id=club.provider_id,
                competition_provider_id=competition.provider_id,
                season_year=sport_season.year,
            ),
        )
        players = client.get(
            "/players",
            {"team": club.provider_id, "season": sport_season.year},
        )
        players_batches.append(
            PlayersBatch(
                envelope=players,
                club_provider_id=club.provider_id,
                season_year=sport_season.year,
            ),
        )
        transfers = client.get("/transfers", {"team": club.provider_id})
        if transfers.results > 0:
            transfer_envelopes.append(transfers)
        if on_progress is not None:
            on_progress(index, max(total, 1), club.name)

    return sync_roster(
        session,
        squad_batches=squad_batches,
        players_batches=players_batches,
        transfers_envelopes=transfer_envelopes,
        league_ids=league_ids,
        store_snapshots=store_snapshots,
    )
