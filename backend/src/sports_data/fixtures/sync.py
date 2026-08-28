"""Idempotent sync of fixtures, events, lineups and player stats (EP04-05)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from leagues.models.competition import Competition
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
    PlayerMatchStat,
)
from sports_data.normalization.events import normalize_scoring_events
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.constants import MVP_LEAGUE_IDS, PROVIDER_NAME
from sports_data.provider.mapping import (
    map_fixtures,
    map_match_events,
    map_official_lineups,
    map_player_match_stats,
)
from sports_data.provider.snapshots import store_provider_snapshot
from sports_data.provider.types import (
    MappedFixture,
    MappedMatchEvent,
    MappedOfficialLineup,
    MappedPlayerMatchStat,
    ProviderEnvelope,
)
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

FIXTURE_SYNC_RUNS_TOTAL = "fixture_sync_runs_total"
FIXTURE_SYNC_ENTITIES_TOTAL = "fixture_sync_entities_total"
FIXTURE_SYNC_DURATION_SECONDS = "fixture_sync_duration_seconds"

UpsertResult = str  # created | updated | unchanged | corrected | retracted | skipped_*


@dataclass
class FixtureSyncCounters:
    fixtures_created: int = 0
    fixtures_updated: int = 0
    fixtures_unchanged: int = 0
    fixtures_skipped_missing_club: int = 0
    fixtures_skipped_missing_season: int = 0
    events_created: int = 0
    events_updated: int = 0
    events_unchanged: int = 0
    events_corrected: int = 0
    events_retracted: int = 0
    lineups_created: int = 0
    lineups_updated: int = 0
    lineups_unchanged: int = 0
    lineup_entries_created: int = 0
    lineup_entries_updated: int = 0
    lineup_entries_unchanged: int = 0
    lineup_entries_removed: int = 0
    stats_created: int = 0
    stats_updated: int = 0
    stats_unchanged: int = 0
    stats_corrected: int = 0
    athletes_created: int = 0
    athletes_unchanged: int = 0
    seasons_created: int = 0
    snapshots_stored: int = 0
    snapshots_deduped: int = 0

    def incr_entity(self, entity: str, result: UpsertResult) -> None:
        attr = f"{entity}_{result}"
        if hasattr(self, attr):
            setattr(self, attr, getattr(self, attr) + 1)
        get_metrics().incr(
            FIXTURE_SYNC_ENTITIES_TOTAL,
            labels={"provider": PROVIDER_NAME, "entity": entity, "result": result},
        )


@dataclass
class FixtureSyncResult:
    counters: FixtureSyncCounters = field(default_factory=FixtureSyncCounters)


@dataclass(frozen=True)
class FixtureDetailBatch:
    """Optional detail envelopes for one fixture (events / lineups / players)."""

    fixture_provider_id: int
    events_envelope: ProviderEnvelope | None = None
    lineups_envelope: ProviderEnvelope | None = None
    players_envelope: ProviderEnvelope | None = None


def _touch_updated_at(row: Any) -> None:
    if hasattr(row, "updated_at"):
        row.updated_at = datetime.now(UTC)


def _maybe_store_snapshot(
    session: Session,
    envelope: ProviderEnvelope,
    counters: FixtureSyncCounters,
    *,
    store_snapshots: bool,
) -> None:
    if not store_snapshots:
        return
    stored, created = store_provider_snapshot(session, envelope)
    if created:
        counters.snapshots_stored += 1
    else:
        counters.snapshots_deduped += 1
    _ = stored


def _resolve_club(session: Session, provider_id: int | None) -> Club | None:
    if provider_id is None:
        return None
    return session.execute(
        select(Club).where(Club.provider_id == provider_id),
    ).scalar_one_or_none()


def _resolve_or_create_sport_season(
    session: Session,
    *,
    competition_provider_id: int,
    season_year: int,
    counters: FixtureSyncCounters,
    create_if_missing: bool = True,
) -> SportSeason | None:
    competition = session.execute(
        select(Competition).where(Competition.provider_id == competition_provider_id),
    ).scalar_one_or_none()
    if competition is None:
        return None
    row = session.execute(
        select(SportSeason).where(
            SportSeason.competition_id == competition.id,
            SportSeason.year == season_year,
        ),
    ).scalar_one_or_none()
    if row is not None:
        return row
    if not create_if_missing:
        return None
    row = SportSeason(
        competition_id=competition.id,
        year=season_year,
        is_current=False,
    )
    session.add(row)
    session.flush()
    counters.incr_entity("seasons", "created")
    return row


def _ensure_athlete(
    session: Session,
    *,
    provider_id: int | None,
    canonical_name: str | None,
    counters: FixtureSyncCounters,
) -> Athlete | None:
    if provider_id is None:
        return None
    row = session.execute(
        select(Athlete).where(Athlete.provider_id == provider_id),
    ).scalar_one_or_none()
    if row is not None:
        return row
    name = (canonical_name or f"athlete:{provider_id}").strip() or f"athlete:{provider_id}"
    row = Athlete(provider_id=provider_id, canonical_name=name[:160])
    session.add(row)
    session.flush()
    counters.incr_entity("athletes", "created")
    return row


def upsert_fixture(
    session: Session,
    mapped: MappedFixture,
    counters: FixtureSyncCounters,
    *,
    create_missing_season: bool = True,
) -> Fixture | None:
    home = _resolve_club(session, mapped.home_club_provider_id)
    away = _resolve_club(session, mapped.away_club_provider_id)
    if home is None or away is None:
        counters.incr_entity("fixtures", "skipped_missing_club")
        return None
    season = _resolve_or_create_sport_season(
        session,
        competition_provider_id=mapped.competition_provider_id,
        season_year=mapped.season_year,
        counters=counters,
        create_if_missing=create_missing_season,
    )
    if season is None:
        counters.incr_entity("fixtures", "skipped_missing_season")
        return None

    row = session.execute(
        select(Fixture).where(Fixture.provider_id == mapped.provider_id),
    ).scalar_one_or_none()
    if row is None:
        row = Fixture(
            provider_id=mapped.provider_id,
            sport_season_id=season.id,
            home_club_id=home.id,
            away_club_id=away.id,
            kickoff_at=mapped.kickoff_at,
            status_short=mapped.status_short,
            status_elapsed=mapped.status_elapsed,
            home_goals=mapped.home_goals,
            away_goals=mapped.away_goals,
            round_label=mapped.round_label,
        )
        session.add(row)
        session.flush()
        counters.incr_entity("fixtures", "created")
        return row

    fields = {
        "sport_season_id": season.id,
        "home_club_id": home.id,
        "away_club_id": away.id,
        "kickoff_at": mapped.kickoff_at,
        "status_short": mapped.status_short,
        "status_elapsed": mapped.status_elapsed,
        "home_goals": mapped.home_goals,
        "away_goals": mapped.away_goals,
        "round_label": mapped.round_label,
    }
    changed = False
    for key, value in fields.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        _touch_updated_at(row)
        counters.incr_entity("fixtures", "updated")
    else:
        counters.incr_entity("fixtures", "unchanged")
    return row


def _apply_event_fields(row: MatchEvent, values: dict[str, Any]) -> bool:
    changed = False
    for key, value in values.items():
        current = getattr(row, key)
        if current != value:
            setattr(row, key, value)
            changed = True
    return changed


def upsert_match_event(
    session: Session,
    *,
    fixture: Fixture,
    mapped: MappedMatchEvent,
    counters: FixtureSyncCounters,
    scoring_kind: str | None = None,
    status: str = "timeline",
    sources: list[str] | None = None,
    anomaly_codes: list[str] | None = None,
) -> MatchEvent:
    athlete = _ensure_athlete(
        session,
        provider_id=mapped.athlete_provider_id,
        canonical_name=None,
        counters=counters,
    )
    related = _ensure_athlete(
        session,
        provider_id=mapped.related_athlete_provider_id,
        canonical_name=None,
        counters=counters,
    )
    club = _resolve_club(session, mapped.club_provider_id)
    values = {
        "fixture_id": fixture.id,
        "athlete_id": athlete.id if athlete else None,
        "related_athlete_id": related.id if related else None,
        "club_id": club.id if club else None,
        "athlete_provider_id": mapped.athlete_provider_id,
        "related_athlete_provider_id": mapped.related_athlete_provider_id,
        "club_provider_id": mapped.club_provider_id,
        "event_type": mapped.event_type,
        "event_detail": mapped.event_detail,
        "scoring_kind": scoring_kind,
        "status": status,
        "minute_elapsed": mapped.minute_elapsed,
        "minute_extra": mapped.minute_extra,
        "comments": mapped.comments,
        "sources": sources or ["events"],
        "anomaly_codes": anomaly_codes or [],
        "is_active": True,
        "retracted_at": None,
    }

    row = session.execute(
        select(MatchEvent).where(MatchEvent.provider_event_key == mapped.provider_event_key),
    ).scalar_one_or_none()
    if row is None:
        row = MatchEvent(provider_event_key=mapped.provider_event_key, **values)
        session.add(row)
        session.flush()
        counters.incr_entity("events", "created")
        return row

    was_retracted = not row.is_active
    changed = _apply_event_fields(row, values)
    if was_retracted or changed:
        _touch_updated_at(row)
        counters.incr_entity("events", "corrected")
    else:
        counters.incr_entity("events", "unchanged")
    return row


def upsert_normalized_scoring_event(
    session: Session,
    *,
    fixture: Fixture,
    provider_event_key: str,
    event_type: str,
    event_detail: str | None,
    athlete_provider_id: int | None,
    related_athlete_provider_id: int | None,
    club_provider_id: int | None,
    minute_elapsed: int | None,
    minute_extra: int | None,
    scoring_kind: str,
    status: str,
    sources: list[str],
    anomaly_codes: list[str],
    counters: FixtureSyncCounters,
) -> MatchEvent:
    mapped = MappedMatchEvent(
        provider_event_key=provider_event_key,
        fixture_provider_id=fixture.provider_id,
        event_type=event_type,
        event_detail=event_detail,
        athlete_provider_id=athlete_provider_id,
        related_athlete_provider_id=related_athlete_provider_id,
        club_provider_id=club_provider_id,
        minute_elapsed=minute_elapsed,
        minute_extra=minute_extra,
        comments=None,
    )
    return upsert_match_event(
        session,
        fixture=fixture,
        mapped=mapped,
        counters=counters,
        scoring_kind=scoring_kind,
        status=status,
        sources=sources,
        anomaly_codes=anomaly_codes,
    )


def retract_missing_events(
    session: Session,
    *,
    fixture_id: UUID,
    seen_keys: set[str],
    counters: FixtureSyncCounters,
    source_prefix: str = "events",
) -> None:
    """Mark active timeline events absent from the latest payload as retracted."""
    rows = (
        session.execute(
            select(MatchEvent).where(
                MatchEvent.fixture_id == fixture_id,
                MatchEvent.is_active.is_(True),
            ),
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for row in rows:
        sources = row.sources if isinstance(row.sources, list) else []
        if source_prefix not in sources and not any(
            isinstance(s, str) and s.startswith(source_prefix) for s in sources
        ):
            continue
        if row.provider_event_key in seen_keys:
            continue
        # Scoring-only keys (assist siblings / stats) are managed separately.
        if "|goal" in row.provider_event_key or "|assist" in row.provider_event_key:
            if row.provider_event_key.startswith("players|"):
                continue
        if row.provider_event_key.startswith("players|"):
            continue
        if not row.provider_event_key.endswith("|primary"):
            continue
        row.is_active = False
        row.retracted_at = now
        _touch_updated_at(row)
        counters.incr_entity("events", "retracted")


def upsert_official_lineup(
    session: Session,
    *,
    fixture: Fixture,
    mapped: MappedOfficialLineup,
    counters: FixtureSyncCounters,
) -> OfficialLineup | None:
    club = _resolve_club(session, mapped.club_provider_id)
    if club is None:
        return None

    row = session.execute(
        select(OfficialLineup).where(
            OfficialLineup.fixture_id == fixture.id,
            OfficialLineup.club_id == club.id,
        ),
    ).scalar_one_or_none()
    # Istante di acquisizione: prova che il dato esisteva prima di una
    # decisione automatica (ADR-0005). Impostato una sola volta alla prima
    # comparsa della distinta, così una ri-sincronizzazione non lo "ringiovanisce".
    fetched_at = datetime.now(UTC)

    if row is None:
        row = OfficialLineup(
            fixture_id=fixture.id,
            club_id=club.id,
            formation=mapped.formation,
            fetched_at=fetched_at,
        )
        session.add(row)
        session.flush()
        counters.incr_entity("lineups", "created")
    else:
        if row.fetched_at is None:
            row.fetched_at = fetched_at
        if row.formation != mapped.formation:
            row.formation = mapped.formation
            _touch_updated_at(row)
            counters.incr_entity("lineups", "updated")
        else:
            counters.incr_entity("lineups", "unchanged")

    seen_provider_ids: set[int] = set()
    for entry in mapped.entries:
        seen_provider_ids.add(entry.athlete_provider_id)
        athlete = _ensure_athlete(
            session,
            provider_id=entry.athlete_provider_id,
            canonical_name=entry.athlete_name,
            counters=counters,
        )
        existing = session.execute(
            select(OfficialLineupEntry).where(
                OfficialLineupEntry.lineup_id == row.id,
                OfficialLineupEntry.athlete_provider_id == entry.athlete_provider_id,
            ),
        ).scalar_one_or_none()
        fields = {
            "athlete_id": athlete.id if athlete else None,
            "is_starter": entry.is_starter,
            "shirt_number": entry.shirt_number,
            "position_raw": entry.position_raw,
            "grid": entry.grid,
            "sort_order": entry.sort_order,
        }
        if existing is None:
            session.add(
                OfficialLineupEntry(
                    lineup_id=row.id,
                    athlete_provider_id=entry.athlete_provider_id,
                    **fields,
                )
            )
            counters.incr_entity("lineup_entries", "created")
        else:
            changed = False
            for key, value in fields.items():
                if getattr(existing, key) != value:
                    setattr(existing, key, value)
                    changed = True
            if changed:
                _touch_updated_at(existing)
                counters.incr_entity("lineup_entries", "updated")
            else:
                counters.incr_entity("lineup_entries", "unchanged")

    stale = (
        session.execute(
            select(OfficialLineupEntry).where(
                OfficialLineupEntry.lineup_id == row.id,
                OfficialLineupEntry.athlete_provider_id.not_in(seen_provider_ids or {-1}),
            ),
        )
        .scalars()
        .all()
    )
    for entry_row in stale:
        session.delete(entry_row)
        counters.incr_entity("lineup_entries", "removed")
    session.flush()
    return row


def upsert_player_match_stat(
    session: Session,
    *,
    fixture: Fixture,
    mapped: MappedPlayerMatchStat,
    counters: FixtureSyncCounters,
) -> PlayerMatchStat:
    athlete = _ensure_athlete(
        session,
        provider_id=mapped.athlete_provider_id,
        canonical_name=mapped.athlete_name,
        counters=counters,
    )
    club = _resolve_club(session, mapped.club_provider_id)
    row = session.execute(
        select(PlayerMatchStat).where(
            PlayerMatchStat.fixture_id == fixture.id,
            PlayerMatchStat.athlete_provider_id == mapped.athlete_provider_id,
        ),
    ).scalar_one_or_none()
    fields = {
        "athlete_id": athlete.id if athlete else None,
        "club_id": club.id if club else None,
        "minutes": mapped.minutes,
        "position_raw": mapped.position_raw,
        "is_substitute": mapped.is_substitute,
        "provider_rating": mapped.provider_rating,
        "stats_json": mapped.stats,
        "stats_hash": mapped.stats_hash,
    }
    if row is None:
        row = PlayerMatchStat(
            fixture_id=fixture.id,
            athlete_provider_id=mapped.athlete_provider_id,
            **fields,
        )
        session.add(row)
        session.flush()
        counters.incr_entity("stats", "created")
        return row

    hash_changed = row.stats_hash != mapped.stats_hash
    changed = False
    for key, value in fields.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        _touch_updated_at(row)
        counters.incr_entity("stats", "corrected" if hash_changed else "updated")
    else:
        counters.incr_entity("stats", "unchanged")
    return row


def sync_fixture_details(
    session: Session,
    *,
    fixture: Fixture,
    events_envelope: ProviderEnvelope | None = None,
    lineups_envelope: ProviderEnvelope | None = None,
    players_envelope: ProviderEnvelope | None = None,
    store_snapshots: bool = True,
    counters: FixtureSyncCounters | None = None,
) -> FixtureSyncResult:
    """Sync events, lineups and player stats for one fixture."""
    result = FixtureSyncResult(counters=counters or FixtureSyncCounters())
    c = result.counters
    events_payload: dict[str, Any] | None = None
    players_payload: dict[str, Any] | None = None

    if events_envelope is not None:
        _maybe_store_snapshot(session, events_envelope, c, store_snapshots=store_snapshots)
        events_payload = events_envelope.raw or {
            "response": events_envelope.response,
            "parameters": events_envelope.parameters,
        }
        seen: set[str] = set()
        for mapped in map_match_events(
            events_envelope,
            fixture_provider_id=fixture.provider_id,
        ):
            seen.add(mapped.provider_event_key)
            upsert_match_event(session, fixture=fixture, mapped=mapped, counters=c)
        retract_missing_events(
            session,
            fixture_id=fixture.id,
            seen_keys=seen,
            counters=c,
        )

    if lineups_envelope is not None:
        _maybe_store_snapshot(session, lineups_envelope, c, store_snapshots=store_snapshots)
        for mapped in map_official_lineups(
            lineups_envelope,
            fixture_provider_id=fixture.provider_id,
        ):
            upsert_official_lineup(session, fixture=fixture, mapped=mapped, counters=c)

    if players_envelope is not None:
        _maybe_store_snapshot(session, players_envelope, c, store_snapshots=store_snapshots)
        players_payload = players_envelope.raw or {
            "response": players_envelope.response,
            "parameters": players_envelope.parameters,
        }
        for mapped in map_player_match_stats(
            players_envelope,
            fixture_provider_id=fixture.provider_id,
        ):
            upsert_player_match_stat(session, fixture=fixture, mapped=mapped, counters=c)

    if events_payload is not None or players_payload is not None:
        normalized = normalize_scoring_events(
            fixture_id=fixture.provider_id,
            events_payload=events_payload,
            players_payload=players_payload,
        )
        for event in normalized.events:
            upsert_normalized_scoring_event(
                session,
                fixture=fixture,
                provider_event_key=event.provider_event_key,
                event_type=event.raw_type or event.kind.value,
                event_detail=event.raw_detail,
                athlete_provider_id=event.player_id,
                related_athlete_provider_id=event.related_player_id,
                club_provider_id=event.team_id,
                minute_elapsed=event.minute_elapsed,
                minute_extra=event.minute_extra,
                scoring_kind=event.kind.value,
                status=event.status.value,
                sources=list(event.sources),
                anomaly_codes=[code.value for code in event.anomaly_codes],
                counters=c,
            )
    return result


def sync_fixtures(
    session: Session,
    *,
    fixtures_envelopes: Sequence[ProviderEnvelope] | None = None,
    detail_batches: Sequence[FixtureDetailBatch] | None = None,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
    create_missing_season: bool = True,
) -> FixtureSyncResult:
    """Atomic unit of work: calendar fixtures then optional match details."""
    metrics = get_metrics()
    labels = {"provider": PROVIDER_NAME}
    counters = FixtureSyncCounters()
    result = FixtureSyncResult(counters=counters)
    allowed = frozenset(league_ids)
    fixture_by_provider: dict[int, Fixture] = {}
    try:
        with Timer(metrics, FIXTURE_SYNC_DURATION_SECONDS, labels=labels):
            for envelope in fixtures_envelopes or ():
                _maybe_store_snapshot(session, envelope, counters, store_snapshots=store_snapshots)
                for mapped in map_fixtures(envelope):
                    if mapped.competition_provider_id not in allowed:
                        continue
                    row = upsert_fixture(
                        session,
                        mapped,
                        counters,
                        create_missing_season=create_missing_season,
                    )
                    if row is not None:
                        fixture_by_provider[mapped.provider_id] = row

            for batch in detail_batches or ():
                fixture = fixture_by_provider.get(batch.fixture_provider_id)
                if fixture is None:
                    fixture = session.execute(
                        select(Fixture).where(Fixture.provider_id == batch.fixture_provider_id),
                    ).scalar_one_or_none()
                if fixture is None:
                    continue
                sync_fixture_details(
                    session,
                    fixture=fixture,
                    events_envelope=batch.events_envelope,
                    lineups_envelope=batch.lineups_envelope,
                    players_envelope=batch.players_envelope,
                    store_snapshots=store_snapshots,
                    counters=counters,
                )

        metrics.incr(FIXTURE_SYNC_RUNS_TOTAL, labels={**labels, "status": "ok"})
        logger.info(
            "fixture_sync_ok",
            extra={
                "provider": PROVIDER_NAME,
                "fixtures_created": counters.fixtures_created,
                "events_created": counters.events_created,
                "events_retracted": counters.events_retracted,
                "stats_created": counters.stats_created,
            },
        )
    except Exception:
        metrics.incr(FIXTURE_SYNC_RUNS_TOTAL, labels={**labels, "status": "error"})
        logger.exception("fixture_sync_failed", extra={"provider": PROVIDER_NAME})
        raise
    return result


def sync_mvp_fixtures_with_client(
    session: Session,
    client: ApiFootballClient,
    *,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    store_snapshots: bool = True,
    include_details: bool = True,
    max_fixtures_per_league: int | None = None,
) -> FixtureSyncResult:
    """Fetch calendar (+ optional details) for current MVP competition seasons."""
    allowed = frozenset(league_ids)
    fixtures_envelopes: list[ProviderEnvelope] = []
    detail_batches: list[FixtureDetailBatch] = []

    season_rows = session.scalars(
        select(SportSeason)
        .join(Competition)
        .where(Competition.provider_id.in_(allowed), SportSeason.is_current.is_(True)),
    ).all()

    for sport_season in season_rows:
        competition = session.get(Competition, sport_season.competition_id)
        if competition is None:
            continue
        params: dict[str, Any] = {
            "league": competition.provider_id,
            "season": sport_season.year,
        }
        envelope = client.get("/fixtures", params)
        fixtures_envelopes.append(envelope)
        if not include_details:
            continue
        mapped_list = map_fixtures(envelope)
        if max_fixtures_per_league is not None:
            mapped_list = mapped_list[:max_fixtures_per_league]
        for mapped in mapped_list:
            events = client.get("/fixtures/events", {"fixture": mapped.provider_id})
            lineups = client.get("/fixtures/lineups", {"fixture": mapped.provider_id})
            players = client.get("/fixtures/players", {"fixture": mapped.provider_id})
            detail_batches.append(
                FixtureDetailBatch(
                    fixture_provider_id=mapped.provider_id,
                    events_envelope=events,
                    lineups_envelope=lineups,
                    players_envelope=players,
                ),
            )

    return sync_fixtures(
        session,
        fixtures_envelopes=fixtures_envelopes,
        detail_batches=detail_batches,
        league_ids=league_ids,
        store_snapshots=store_snapshots,
    )
