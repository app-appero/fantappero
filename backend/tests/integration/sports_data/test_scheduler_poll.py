"""Integration tests for sports poll cycles — lock, idempotency, degrade (EP04-06)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from observability.metrics import get_metrics, reset_metrics
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
    PlayerMatchStat,
)
from sports_data.fixtures.sync import FixtureDetailBatch
from sports_data.provider.envelope import parse_envelope
from sports_data.provider.types import ProviderRateLimit
from sports_data.roster.models import Athlete
from sports_data.scheduler.locks import InMemoryJobLock
from sports_data.scheduler.models import SportsPollRun
from sports_data.scheduler.quota import QuotaMode
from sports_data.scheduler.runner import (
    SCHEDULER_RUNS_TOTAL,
    run_poll_cycle,
    should_skip_for_interval,
)
from sports_data.scheduler.windows import PollWindow

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
MATCH = DATASET / "matches" / "39" / "1035055"


@pytest.fixture(autouse=True)
def clean_tables(session: Session) -> None:
    session.execute(delete(SportsPollRun))
    session.execute(delete(OfficialLineupEntry))
    session.execute(delete(OfficialLineup))
    session.execute(delete(PlayerMatchStat))
    session.execute(delete(MatchEvent))
    session.execute(delete(Fixture))
    session.execute(delete(Athlete))
    session.commit()


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def _seed_catalog(session: Session) -> None:
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    teams = parse_envelope(_load("reference/teams.json"), endpoint="/teams", http_status=200)
    sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=[TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026)],
    )


def _match_batches() -> tuple[list, list[FixtureDetailBatch]]:
    fixtures_env = parse_envelope(
        _load("matches/39/1035055/fixtures.json"),
        endpoint="/fixtures",
        http_status=200,
        rate_limit=ProviderRateLimit(limit=100, remaining=80),
    )
    events_env = parse_envelope(
        _load("matches/39/1035055/fixtures_events.json"),
        endpoint="/fixtures/events",
        http_status=200,
    )
    lineups_env = parse_envelope(
        _load("matches/39/1035055/fixtures_lineups.json"),
        endpoint="/fixtures/lineups",
        http_status=200,
    )
    players_env = parse_envelope(
        _load("matches/39/1035055/fixtures_players.json"),
        endpoint="/fixtures/players",
        http_status=200,
    )
    return [fixtures_env], [
        FixtureDetailBatch(
            fixture_provider_id=1035055,
            events_envelope=events_env,
            lineups_envelope=lineups_env,
            players_envelope=players_env,
        ),
    ]


def test_poll_cycle_idempotent_with_sample_payloads(session: Session) -> None:
    reset_metrics()
    _seed_catalog(session)
    session.commit()
    fixtures_envs, details = _match_batches()
    lock = InMemoryJobLock()

    first = run_poll_cycle(
        session,
        PollWindow.POST_MATCH,
        lock=lock,
        fixtures_envelopes=fixtures_envs,
        detail_batches=details,
        rate_limit=ProviderRateLimit(limit=100, remaining=80),
        respect_interval=False,
        now=datetime(2023, 8, 20, 16, 0, tzinfo=UTC),
    )
    session.commit()
    assert first.status == "ok"
    assert first.sync is not None
    assert first.sync.counters.fixtures_created == 1
    fixture_id = session.scalar(select(Fixture.id).where(Fixture.provider_id == 1035055))
    events_first = session.scalar(select(func.count()).select_from(MatchEvent))

    second = run_poll_cycle(
        session,
        PollWindow.POST_MATCH,
        lock=lock,
        fixtures_envelopes=fixtures_envs,
        detail_batches=details,
        rate_limit=ProviderRateLimit(limit=100, remaining=80),
        respect_interval=False,
        now=datetime(2023, 8, 20, 16, 5, tzinfo=UTC),
    )
    session.commit()
    assert second.status == "ok"
    assert second.sync is not None
    assert second.sync.counters.fixtures_created == 0
    assert session.scalar(select(Fixture.id).where(Fixture.provider_id == 1035055)) == fixture_id
    assert session.scalar(select(func.count()).select_from(MatchEvent)) == events_first
    runs = session.scalars(select(SportsPollRun)).all()
    assert len(runs) == 2
    assert (
        get_metrics().get_counter(
            SCHEDULER_RUNS_TOTAL,
            labels={"provider": "api-football-v3", "window": "post_match", "status": "ok"},
        )
        == 2.0
    )


def test_concurrent_lock_skips_second_job(session: Session) -> None:
    reset_metrics()
    lock = InMemoryJobLock()
    token = lock.try_acquire("live", ttl_seconds=60)
    assert token is not None

    result = run_poll_cycle(
        session,
        PollWindow.LIVE,
        lock=lock,
        respect_interval=False,
        fetch_from_provider=False,
    )
    session.commit()
    assert result.status == "skipped_lock"
    run = session.scalar(select(SportsPollRun).where(SportsPollRun.status == "skipped_lock"))
    assert run is not None
    lock.release("live", token)


def test_degraded_mode_is_observable(session: Session) -> None:
    reset_metrics()
    _seed_catalog(session)
    session.commit()
    fixtures_envs, details = _match_batches()
    lock = InMemoryJobLock()

    result = run_poll_cycle(
        session,
        PollWindow.POST_MATCH,
        lock=lock,
        fixtures_envelopes=fixtures_envs,
        detail_batches=details,
        rate_limit=ProviderRateLimit(limit=100, remaining=10),
        respect_interval=False,
        now=datetime(2023, 8, 20, 16, 0, tzinfo=UTC),
    )
    session.commit()
    assert result.quota_mode == QuotaMode.DEGRADE
    assert result.status == "degraded_ok"
    run = session.scalar(select(SportsPollRun))
    assert run is not None
    assert run.quota_mode == "degrade"
    assert run.status == "degraded_ok"
    assert run.details.get("degraded") is True


def test_critical_only_skips_pre_match(session: Session) -> None:
    lock = InMemoryJobLock()
    result = run_poll_cycle(
        session,
        PollWindow.PRE_MATCH,
        lock=lock,
        rate_limit=ProviderRateLimit(limit=100, remaining=2),
        respect_interval=False,
        fetch_from_provider=False,
    )
    session.commit()
    assert result.status == "skipped_quota"
    assert result.quota_mode == QuotaMode.CRITICAL_ONLY


def test_interval_gate_under_degrade() -> None:
    last = datetime(2023, 8, 20, 15, 0, tzinfo=UTC)
    now = last + timedelta(seconds=90)
    assert (
        should_skip_for_interval(
            window=PollWindow.LIVE,
            mode=QuotaMode.OK,
            last_ok_at=last,
            now=now,
        )
        is False
    )
    assert (
        should_skip_for_interval(
            window=PollWindow.LIVE,
            mode=QuotaMode.DEGRADE,
            last_ok_at=last,
            now=now,
        )
        is True
    )
