"""Idempotent sync of competitions, seasons and clubs (EP04-02)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from leagues.models.competition import Competition
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.constants import MVP_LEAGUE_IDS, PROVIDER_NAME
from sports_data.provider.mapping import map_clubs, map_competitions, map_seasons
from sports_data.provider.snapshots import store_provider_snapshot
from sports_data.provider.types import (
    MappedClub,
    MappedCompetition,
    MappedSeason,
    ProviderEnvelope,
)

logger = get_logger(__name__)

CATALOG_SYNC_RUNS_TOTAL = "catalog_sync_runs_total"
CATALOG_SYNC_ENTITIES_TOTAL = "catalog_sync_entities_total"
CATALOG_SYNC_DURATION_SECONDS = "catalog_sync_duration_seconds"

UpsertResult = str  # created | updated | unchanged


@dataclass
class CatalogSyncCounters:
    competitions_created: int = 0
    competitions_updated: int = 0
    competitions_unchanged: int = 0
    seasons_created: int = 0
    seasons_updated: int = 0
    seasons_unchanged: int = 0
    clubs_created: int = 0
    clubs_updated: int = 0
    clubs_unchanged: int = 0
    clubs_skipped_national: int = 0
    memberships_created: int = 0
    memberships_unchanged: int = 0
    snapshots_stored: int = 0
    snapshots_deduped: int = 0

    def incr_entity(self, entity: str, result: UpsertResult) -> None:
        attr = f"{entity}_{result}"
        if hasattr(self, attr):
            setattr(self, attr, getattr(self, attr) + 1)
        metrics = get_metrics()
        metrics.incr(
            CATALOG_SYNC_ENTITIES_TOTAL,
            labels={"provider": PROVIDER_NAME, "entity": entity, "result": result},
        )


@dataclass
class CatalogSyncResult:
    counters: CatalogSyncCounters = field(default_factory=CatalogSyncCounters)
    competition_ids_by_provider: dict[int, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TeamsBatch:
    """Teams envelope scoped to a competition season."""

    envelope: ProviderEnvelope
    competition_provider_id: int
    season_year: int


def _touch_updated_at(row: Any) -> None:
    if hasattr(row, "updated_at"):
        row.updated_at = datetime.now(UTC)


def upsert_competition(
    session: Session,
    mapped: MappedCompetition,
    counters: CatalogSyncCounters,
) -> Competition:
    row = session.execute(
        select(Competition).where(Competition.provider_id == mapped.provider_id),
    ).scalar_one_or_none()
    if row is None:
        row = Competition(
            provider_id=mapped.provider_id,
            name=mapped.name,
            country=mapped.country,
        )
        session.add(row)
        session.flush()
        counters.incr_entity("competitions", "created")
        return row

    changed = False
    if row.name != mapped.name:
        row.name = mapped.name
        changed = True
    if row.country != mapped.country:
        row.country = mapped.country
        changed = True
    if changed:
        _touch_updated_at(row)
        counters.incr_entity("competitions", "updated")
    else:
        counters.incr_entity("competitions", "unchanged")
    return row


def upsert_season(
    session: Session,
    mapped: MappedSeason,
    competition: Competition,
    counters: CatalogSyncCounters,
) -> SportSeason:
    row = session.execute(
        select(SportSeason).where(
            SportSeason.competition_id == competition.id,
            SportSeason.year == mapped.year,
        ),
    ).scalar_one_or_none()
    fields = {
        "is_current": mapped.is_current,
        "start_date": mapped.start_date,
        "end_date": mapped.end_date,
        "coverage_events": mapped.coverage_events,
        "coverage_lineups": mapped.coverage_lineups,
        "coverage_statistics_players": mapped.coverage_statistics_players,
        "coverage_injuries": mapped.coverage_injuries,
        "coverage_predictions": mapped.coverage_predictions,
        "coverage_standings": mapped.coverage_standings,
    }
    if row is None:
        row = SportSeason(competition_id=competition.id, year=mapped.year, **fields)
        session.add(row)
        session.flush()
        counters.incr_entity("seasons", "created")
        return row

    changed = False
    for key, value in fields.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        _touch_updated_at(row)
        counters.incr_entity("seasons", "updated")
    else:
        counters.incr_entity("seasons", "unchanged")
    return row


def upsert_club(
    session: Session,
    mapped: MappedClub,
    counters: CatalogSyncCounters,
) -> Club | None:
    if mapped.national:
        counters.clubs_skipped_national += 1
        get_metrics().incr(
            CATALOG_SYNC_ENTITIES_TOTAL,
            labels={"provider": PROVIDER_NAME, "entity": "clubs", "result": "skipped_national"},
        )
        return None

    row = session.execute(
        select(Club).where(Club.provider_id == mapped.provider_id),
    ).scalar_one_or_none()
    if row is None:
        row = Club(
            provider_id=mapped.provider_id,
            name=mapped.name,
            code=mapped.code,
            country=mapped.country,
            logo_url=mapped.logo_url,
            national=False,
        )
        session.add(row)
        session.flush()
        counters.incr_entity("clubs", "created")
        return row

    changed = False
    if row.name != mapped.name:
        row.name = mapped.name
        changed = True
    if row.code != mapped.code:
        row.code = mapped.code
        changed = True
    if row.country != mapped.country:
        row.country = mapped.country
        changed = True
    if row.logo_url != mapped.logo_url:
        row.logo_url = mapped.logo_url
        changed = True
    if row.national:
        row.national = False
        changed = True
    if changed:
        _touch_updated_at(row)
        counters.incr_entity("clubs", "updated")
    else:
        counters.incr_entity("clubs", "unchanged")
    return row


def ensure_season_club_membership(
    session: Session,
    *,
    sport_season: SportSeason,
    club: Club,
    counters: CatalogSyncCounters,
) -> CompetitionSeasonClub:
    row = session.execute(
        select(CompetitionSeasonClub).where(
            CompetitionSeasonClub.sport_season_id == sport_season.id,
            CompetitionSeasonClub.club_id == club.id,
        ),
    ).scalar_one_or_none()
    if row is None:
        row = CompetitionSeasonClub(sport_season_id=sport_season.id, club_id=club.id)
        session.add(row)
        session.flush()
        counters.incr_entity("memberships", "created")
        return row
    counters.incr_entity("memberships", "unchanged")
    return row


def _maybe_store_snapshot(
    session: Session,
    envelope: ProviderEnvelope,
    counters: CatalogSyncCounters,
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


def sync_competitions_and_seasons(
    session: Session,
    envelope: ProviderEnvelope,
    *,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
    counters: CatalogSyncCounters | None = None,
) -> CatalogSyncResult:
    """Upsert MVP competitions and their seasons from a ``/leagues`` envelope."""
    result = CatalogSyncResult(counters=counters or CatalogSyncCounters())
    allowed = frozenset(league_ids)
    _maybe_store_snapshot(session, envelope, result.counters, store_snapshots=store_snapshots)

    by_provider: dict[int, Competition] = {}
    for mapped in map_competitions(envelope):
        if mapped.provider_id not in allowed:
            continue
        competition = upsert_competition(session, mapped, result.counters)
        by_provider[mapped.provider_id] = competition
        result.competition_ids_by_provider[mapped.provider_id] = competition.id

    for mapped in map_seasons(envelope):
        if mapped.competition_provider_id not in allowed:
            continue
        competition = by_provider.get(mapped.competition_provider_id)
        if competition is None:
            competition = session.execute(
                select(Competition).where(
                    Competition.provider_id == mapped.competition_provider_id,
                ),
            ).scalar_one_or_none()
            if competition is None:
                logger.warning(
                    "catalog_season_skipped_missing_competition",
                    extra={
                        "provider": PROVIDER_NAME,
                        "competition_provider_id": mapped.competition_provider_id,
                        "season_year": mapped.year,
                    },
                )
                continue
            by_provider[mapped.competition_provider_id] = competition
            result.competition_ids_by_provider[mapped.competition_provider_id] = competition.id
        upsert_season(session, mapped, competition, result.counters)

    logger.info(
        "catalog_competitions_seasons_synced",
        extra={
            "provider": PROVIDER_NAME,
            "competitions": len(by_provider),
            "created": result.counters.competitions_created,
            "updated": result.counters.competitions_updated,
            "seasons_created": result.counters.seasons_created,
            "seasons_updated": result.counters.seasons_updated,
        },
    )
    return result


def sync_clubs_for_season(
    session: Session,
    envelope: ProviderEnvelope,
    *,
    competition_provider_id: int,
    season_year: int,
    store_snapshots: bool = True,
    counters: CatalogSyncCounters | None = None,
) -> CatalogSyncResult:
    """Upsert clubs and season memberships from a ``/teams`` envelope."""
    result = CatalogSyncResult(counters=counters or CatalogSyncCounters())
    _maybe_store_snapshot(session, envelope, result.counters, store_snapshots=store_snapshots)

    competition = session.execute(
        select(Competition).where(Competition.provider_id == competition_provider_id),
    ).scalar_one_or_none()
    if competition is None:
        raise ValueError(
            f"Competizione provider_id={competition_provider_id} assente: "
            "sincronizzare prima il catalogo competizioni",
        )

    sport_season = session.execute(
        select(SportSeason).where(
            SportSeason.competition_id == competition.id,
            SportSeason.year == season_year,
        ),
    ).scalar_one_or_none()
    if sport_season is None:
        raise ValueError(
            f"Stagione {season_year} per competizione provider_id={competition_provider_id} "
            "assente: sincronizzare prima le stagioni",
        )

    result.competition_ids_by_provider[competition_provider_id] = competition.id
    for mapped in map_clubs(envelope):
        club = upsert_club(session, mapped, result.counters)
        if club is None:
            continue
        ensure_season_club_membership(
            session,
            sport_season=sport_season,
            club=club,
            counters=result.counters,
        )

    logger.info(
        "catalog_clubs_synced",
        extra={
            "provider": PROVIDER_NAME,
            "competition_provider_id": competition_provider_id,
            "season_year": season_year,
            "clubs_created": result.counters.clubs_created,
            "clubs_updated": result.counters.clubs_updated,
            "memberships_created": result.counters.memberships_created,
        },
    )
    return result


def sync_catalog(
    session: Session,
    *,
    leagues_envelope: ProviderEnvelope | None = None,
    teams_batches: Sequence[TeamsBatch] | None = None,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
) -> CatalogSyncResult:
    """Atomic catalog unit of work: competitions/seasons then club batches."""
    metrics = get_metrics()
    labels = {"provider": PROVIDER_NAME}
    counters = CatalogSyncCounters()
    result = CatalogSyncResult(counters=counters)
    try:
        with Timer(metrics, CATALOG_SYNC_DURATION_SECONDS, labels=labels):
            if leagues_envelope is not None:
                partial = sync_competitions_and_seasons(
                    session,
                    leagues_envelope,
                    league_ids=league_ids,
                    store_snapshots=store_snapshots,
                    counters=counters,
                )
                result.competition_ids_by_provider.update(partial.competition_ids_by_provider)
            for batch in teams_batches or ():
                if batch.competition_provider_id not in frozenset(league_ids):
                    continue
                partial = sync_clubs_for_season(
                    session,
                    batch.envelope,
                    competition_provider_id=batch.competition_provider_id,
                    season_year=batch.season_year,
                    store_snapshots=store_snapshots,
                    counters=counters,
                )
                result.competition_ids_by_provider.update(partial.competition_ids_by_provider)
        metrics.incr(CATALOG_SYNC_RUNS_TOTAL, labels={**labels, "status": "ok"})
        logger.info(
            "catalog_sync_ok",
            extra={
                "provider": PROVIDER_NAME,
                "competitions_created": counters.competitions_created,
                "seasons_created": counters.seasons_created,
                "clubs_created": counters.clubs_created,
                "memberships_created": counters.memberships_created,
            },
        )
    except Exception:
        metrics.incr(CATALOG_SYNC_RUNS_TOTAL, labels={**labels, "status": "error"})
        logger.exception("catalog_sync_failed", extra={"provider": PROVIDER_NAME})
        raise
    return result


def sync_mvp_catalog_with_client(
    session: Session,
    client: ApiFootballClient,
    *,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
    teams_params: Mapping[str, Any] | None = None,
) -> CatalogSyncResult:
    """Fetch provider ``/leagues`` + ``/teams`` for MVP ids and persist catalog."""
    leagues = client.get("/leagues", {"current": "true"})
    competitions = [c for c in map_competitions(leagues) if c.provider_id in frozenset(league_ids)]
    batches: list[TeamsBatch] = []
    extra = dict(teams_params or {})
    for competition in competitions:
        if competition.season_year is None:
            logger.warning(
                "catalog_teams_skipped_missing_season",
                extra={
                    "provider": PROVIDER_NAME,
                    "competition_provider_id": competition.provider_id,
                },
            )
            continue
        params = {
            "league": competition.provider_id,
            "season": competition.season_year,
            **extra,
        }
        teams = client.get("/teams", params)
        batches.append(
            TeamsBatch(
                envelope=teams,
                competition_provider_id=competition.provider_id,
                season_year=competition.season_year,
            ),
        )
    return sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=batches,
        league_ids=league_ids,
        store_snapshots=store_snapshots,
    )
