"""Integration tests for sports data quality scan / retry (EP04-07)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import delete, select
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
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.provider.envelope import parse_envelope
from sports_data.quality.models import SportsDataQualityIssue, SportsDataSyncRetry
from sports_data.quality.retry import (
    create_retry_audit,
    run_retry,
    sync_single_fixture_offline,
)
from sports_data.quality.scan import (
    QUALITY_SCAN_RUNS_TOTAL,
    scan_quality,
)
from sports_data.quality.types import QualityIssueCode, QualityIssueStatus
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


@pytest.fixture(autouse=True)
def clean_tables(session: Session) -> None:
    session.execute(delete(SportsDataSyncRetry))
    session.execute(delete(SportsDataQualityIssue))
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


def test_quality_scan_detects_missing_and_is_idempotent(session: Session) -> None:
    reset_metrics()
    _seed_catalog(session)
    fixtures_envs, details = _match_batches()
    sync_fixtures(session, fixtures_envelopes=fixtures_envs, detail_batches=details)
    session.commit()

    fixture = session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()

    # Simula gap: rimuovi eventi e stats
    session.execute(delete(MatchEvent).where(MatchEvent.fixture_id == fixture.id))
    session.execute(delete(PlayerMatchStat).where(PlayerMatchStat.fixture_id == fixture.id))
    session.commit()

    first = scan_quality(session, fixture_ids=[fixture.id])
    session.commit()
    assert first.counters.findings >= 2
    assert first.counters.issues_created >= 2

    open_issues = session.execute(
        select(SportsDataQualityIssue).where(
            SportsDataQualityIssue.status == QualityIssueStatus.OPEN.value,
        ),
    ).scalars().all()
    codes = {row.code for row in open_issues}
    assert QualityIssueCode.MISSING_EVENTS.value in codes
    assert QualityIssueCode.MISSING_STATS.value in codes

    second = scan_quality(session, fixture_ids=[fixture.id])
    session.commit()
    assert second.counters.issues_created == 0
    open_after = session.execute(
        select(SportsDataQualityIssue).where(
            SportsDataQualityIssue.status == QualityIssueStatus.OPEN.value,
        ),
    ).scalars().all()
    assert len(open_after) == len(open_issues)
    assert get_metrics().get_counter(
        QUALITY_SCAN_RUNS_TOTAL,
        labels={"provider": "api-football-v3", "status": "ok"},
    ) >= 2


def test_retry_sync_offline_idempotent_and_resolves_gap(session: Session) -> None:
    reset_metrics()
    _seed_catalog(session)
    fixtures_envs, details = _match_batches()
    sync_fixtures(session, fixtures_envelopes=fixtures_envs, detail_batches=details)
    session.commit()

    fixture = session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()
    session.execute(delete(MatchEvent).where(MatchEvent.fixture_id == fixture.id))
    session.commit()

    scan_quality(session, fixture_ids=[fixture.id])
    session.commit()
    issue = session.execute(
        select(SportsDataQualityIssue).where(
            SportsDataQualityIssue.code == QualityIssueCode.MISSING_EVENTS.value,
        ),
    ).scalar_one()

    payloads = {
        "fixtures": fixtures_envs[0],
        "events": details[0].events_envelope,
        "lineups": details[0].lineups_envelope,
        "players": details[0].players_envelope,
    }
    retry = create_retry_audit(
        session,
        fixture_provider_id=1035055,
        fixture_id=fixture.id,
        issue_id=issue.id,
    )
    session.flush()
    first = run_retry(session, retry.id, offline_payloads=payloads)
    session.commit()
    assert first.status == "ok"
    assert first.counters.get("events_created", 0) >= 1

    # Secondo rilancio: mapping/idempotenza — nessun nuovo evento
    retry2 = create_retry_audit(
        session,
        fixture_provider_id=1035055,
        fixture_id=fixture.id,
        issue_id=issue.id,
    )
    session.flush()
    second = run_retry(session, retry2.id, offline_payloads=payloads)
    session.commit()
    assert second.status == "ok"
    assert second.counters.get("events_created", 0) == 0

    scan_quality(session, fixture_ids=[fixture.id])
    session.commit()
    missing = session.execute(
        select(SportsDataQualityIssue).where(
            SportsDataQualityIssue.code == QualityIssueCode.MISSING_EVENTS.value,
        ),
    ).scalar_one()
    assert missing.status == QualityIssueStatus.RESOLVED.value


def test_sync_single_fixture_offline_mapping(session: Session) -> None:
    _seed_catalog(session)
    session.commit()
    fixtures_envs, details = _match_batches()
    result = sync_single_fixture_offline(
        session,
        fixture_provider_id=1035055,
        fixtures_envelope=fixtures_envs[0],
        events_envelope=details[0].events_envelope,
        lineups_envelope=details[0].lineups_envelope,
        players_envelope=details[0].players_envelope,
    )
    session.commit()
    assert result.counters.fixtures_created == 1
    fixture = session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()
    assert fixture.status_short in {"FT", "AET", "PEN", "NS", "1H", "2H", "HT"}
