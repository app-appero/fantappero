"""Integration tests for sports poll cycles — lock, idempotency, degrade (EP04-06)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from leagues.models.competition import Competition
from observability.metrics import get_metrics, reset_metrics
from sports_data.catalog.models import Club, SportSeason
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
    PlayerMatchStat,
)
from sports_data.fixtures.sync import FixtureDetailBatch
from sports_data.provider.client import ApiFootballClient
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


# -- Sonda della quota e quota giornaliera finita (pilota, 23-24/11) ---------------------------


def _status_body(*, current: int, limit_day: int) -> dict:
    """``GET /status`` di API-Football v3: ``response`` è un oggetto."""
    return {
        "get": "status",
        "parameters": [],
        "errors": [],
        "results": 1,
        "paging": {"current": 1, "total": 1},
        "response": {
            "account": {"firstname": "Test", "lastname": "Test", "email": "test@example.com"},
            "subscription": {"plan": "Pro", "end": "2027-06-30T00:00:00+00:00", "active": True},
            "requests": {"current": current, "limit_day": limit_day},
        },
    }


def _empty_body(request: httpx.Request) -> dict:
    return {
        "get": request.url.path.lstrip("/"),
        "parameters": dict(request.url.params),
        "errors": [],
        "results": 0,
        "paging": {"current": 1, "total": 1},
        "response": [],
    }


def _client(handler) -> ApiFootballClient:
    return ApiFootballClient(
        api_key="test-key-not-a-secret",
        base_url="https://provider.test",
        transport=httpx.MockTransport(handler),
        max_retries=0,
        retry_backoff_seconds=0,
        requests_per_minute=10_000,
    )


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (1000, QuotaMode.OK),
        (5800, QuotaMode.WARN),
        (6500, QuotaMode.DEGRADE),
        (7200, QuotaMode.CRITICAL_ONLY),
    ],
)
def test_status_probe_sets_the_quota_mode_from_the_response_object(
    session: Session, current: int, expected: QuotaMode
) -> None:
    """Prima la sonda falliva sempre (``response`` oggetto) e la modalità restava ``ok``."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/status":
            return httpx.Response(200, json=_status_body(current=current, limit_day=7500))
        return httpx.Response(200, json=_empty_body(request))

    with _client(handler) as client:
        result = run_poll_cycle(
            session,
            PollWindow.LATE_CORRECTIONS,
            lock=InMemoryJobLock(),
            client=client,
            respect_interval=False,
        )
    session.commit()
    assert result.quota_mode == expected
    run = session.get(SportsPollRun, result.run_id)
    assert run is not None
    assert run.quota_mode == expected.value
    assert run.details["quota_remaining"] == 7500 - current
    assert run.details["quota_limit"] == 7500


def test_status_probe_failure_names_the_error_in_the_log(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/status":
            return httpx.Response(200, json={"get": "status", "response": "non valida"})
        return httpx.Response(200, json=_empty_body(request))

    with caplog.at_level("WARNING", logger="sports_data.scheduler.runner"):
        with _client(handler) as client:
            result = run_poll_cycle(
                session,
                PollWindow.LATE_CORRECTIONS,
                lock=InMemoryJobLock(),
                client=client,
                respect_interval=False,
            )
    assert result.quota_mode == QuotaMode.OK
    messages = [record.getMessage() for record in caplog.records]
    assert (
        "sports_scheduler_status_probe_failed window=late_corrections error=ProviderResponseError"
        in messages
    )


def test_status_probe_daily_limit_switches_to_critical_only(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _empty_body(request)
        body["errors"] = {"requests": "You have reached the request limit for the day."}
        return httpx.Response(200, json=body)

    with _client(handler) as client:
        result = run_poll_cycle(
            session,
            PollWindow.PRE_MATCH,
            lock=InMemoryJobLock(),
            client=client,
            respect_interval=False,
        )
    assert result.quota_mode == QuotaMode.CRITICAL_ONLY
    assert result.status == "skipped_quota"


def test_late_corrections_poll_first_the_matches_without_player_stats(session: Session) -> None:
    """Il giro delle correzioni tardive chiede al massimo 15 partite: prima quelle ancora senza
    statistiche giocatore (niente voti), non le prime 15 nell'ordine del database."""
    _seed_catalog(session)
    session.commit()
    season = session.scalar(
        select(SportSeason)
        .join(Competition, Competition.id == SportSeason.competition_id)
        .where(Competition.provider_id == 39)
    )
    assert season is not None
    home, away = session.scalars(select(Club).order_by(Club.provider_id).limit(2)).all()
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    kickoff = now - timedelta(hours=10)  # finita da quasi 8 ore: correzioni tardive
    fixtures = []
    for index in range(16):
        fixture = Fixture(
            provider_id=990_001 + index,
            sport_season_id=season.id,
            home_club_id=home.id,
            away_club_id=away.id,
            kickoff_at=kickoff,
            status_short="FT",
        )
        session.add(fixture)
        session.flush()
        fixtures.append(fixture)
    without_stats = fixtures[-1]  # l'ultima inserita: nell'ordine del database resterebbe fuori
    for fixture in fixtures[:-1]:
        for offset, club in enumerate((home, away)):
            session.add(
                PlayerMatchStat(
                    fixture_id=fixture.id,
                    athlete_provider_id=fixture.provider_id * 10 + offset,
                    club_id=club.id,
                    minutes=90,
                    stats_json={},
                    stats_hash=f"late-{fixture.provider_id}-{offset}",
                )
            )
    session.commit()

    requested: set[int] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/status":
            return httpx.Response(200, json=_status_body(current=10, limit_day=7500))
        if request.url.path in {"/fixtures/events", "/fixtures/players"}:
            requested.add(int(request.url.params["fixture"]))
        return httpx.Response(200, json=_empty_body(request))

    with _client(handler) as client:
        result = run_poll_cycle(
            session,
            PollWindow.LATE_CORRECTIONS,
            lock=InMemoryJobLock(),
            client=client,
            respect_interval=False,
            now=now,
        )
    session.commit()
    assert result.fixtures_considered == 15
    assert len(requested) == 15
    assert without_stats.provider_id in requested
