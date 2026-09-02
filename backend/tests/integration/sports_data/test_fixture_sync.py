"""Integration tests for sports fixture sync idempotency (EP04-05)."""

from __future__ import annotations

import copy
import json
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
from sports_data.fixtures.sync import (
    FIXTURE_SYNC_ENTITIES_TOTAL,
    FixtureDetailBatch,
    sync_fixtures,
)
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
MATCH = DATASET / "matches" / "39" / "1035055"


@pytest.fixture(autouse=True)
def clean_fixture_tables(session: Session) -> None:
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


def test_fixture_sync_idempotent_stable_uuids(session: Session) -> None:
    reset_metrics()
    _seed_catalog(session)
    session.commit()

    fixtures_envs, details = _match_batches()
    first = sync_fixtures(session, fixtures_envelopes=fixtures_envs, detail_batches=details)
    session.commit()

    assert first.counters.fixtures_created == 1
    assert first.counters.events_created >= 19
    assert first.counters.lineups_created == 2
    assert first.counters.stats_created >= 20

    fixture = session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()
    fixture_id = fixture.id
    event_count = session.execute(select(func.count()).select_from(MatchEvent)).scalar_one()
    stats_count = session.execute(select(func.count()).select_from(PlayerMatchStat)).scalar_one()

    second = sync_fixtures(session, fixtures_envelopes=fixtures_envs, detail_batches=details)
    session.commit()

    fixture_after = session.execute(
        select(Fixture).where(Fixture.provider_id == 1035055),
    ).scalar_one()
    assert fixture_after.id == fixture_id
    assert second.counters.fixtures_created == 0
    assert second.counters.events_created == 0
    assert second.counters.events_retracted == 0
    assert session.execute(select(func.count()).select_from(MatchEvent)).scalar_one() == event_count
    assert (
        session.execute(select(func.count()).select_from(PlayerMatchStat)).scalar_one()
        == stats_count
    )

    metrics = get_metrics()
    assert (
        metrics.get_counter(
            FIXTURE_SYNC_ENTITIES_TOTAL,
            labels={"provider": "api-football-v3", "entity": "fixtures", "result": "unchanged"},
        )
        >= 1
    )


def test_event_correction_and_retraction_detected(session: Session) -> None:
    _seed_catalog(session)
    session.commit()

    fixtures_envs, details = _match_batches()
    sync_fixtures(session, fixtures_envelopes=fixtures_envs, detail_batches=details)
    session.commit()

    active_before = session.execute(
        select(func.count()).select_from(MatchEvent).where(MatchEvent.is_active.is_(True)),
    ).scalar_one()
    assert active_before >= 19

    # Remove one timeline event and alter another comment → retraction + correction.
    payload = _load("matches/39/1035055/fixtures_events.json")
    altered = copy.deepcopy(payload)
    altered["response"] = list(altered["response"])
    removed = altered["response"].pop(1)  # yellow card Aguerd 13'
    assert removed["detail"] == "Yellow Card"
    altered["response"][0]["comments"] = "Corrected assist note"

    events_env = parse_envelope(altered, endpoint="/fixtures/events", http_status=200)
    result = sync_fixtures(
        session,
        fixtures_envelopes=fixtures_envs,
        detail_batches=[
            FixtureDetailBatch(
                fixture_provider_id=1035055,
                events_envelope=events_env,
            ),
        ],
    )
    session.commit()

    assert result.counters.events_retracted >= 1
    assert result.counters.events_corrected >= 1

    retracted = session.execute(
        select(MatchEvent).where(
            MatchEvent.is_active.is_(False),
            MatchEvent.event_detail == "Yellow Card",
            MatchEvent.minute_elapsed == 13,
        ),
    ).scalars().all()
    assert len(retracted) == 1
    assert retracted[0].retracted_at is not None

    # Re-sync original payload restores retracted event (correction).
    original_events = parse_envelope(
        _load("matches/39/1035055/fixtures_events.json"),
        endpoint="/fixtures/events",
        http_status=200,
    )
    restored = sync_fixtures(
        session,
        fixtures_envelopes=fixtures_envs,
        detail_batches=[
            FixtureDetailBatch(
                fixture_provider_id=1035055,
                events_envelope=original_events,
            ),
        ],
    )
    session.commit()
    assert restored.counters.events_corrected >= 1
    yellow = session.execute(
        select(MatchEvent).where(
            MatchEvent.event_detail == "Yellow Card",
            MatchEvent.minute_elapsed == 13,
            MatchEvent.athlete_provider_id == 21694,
            MatchEvent.provider_event_key.endswith("|primary"),
        ),
    ).scalar_one()
    assert yellow.is_active is True
    assert yellow.retracted_at is None


def test_stats_hash_change_counts_as_correction(session: Session) -> None:
    _seed_catalog(session)
    session.commit()

    fixtures_envs, details = _match_batches()
    sync_fixtures(session, fixtures_envelopes=fixtures_envs, detail_batches=details)
    session.commit()

    payload = _load("matches/39/1035055/fixtures_players.json")
    altered = copy.deepcopy(payload)
    player = altered["response"][0]["players"][0]
    player["statistics"][0]["games"]["minutes"] = 89

    players_env = parse_envelope(altered, endpoint="/fixtures/players", http_status=200)
    result = sync_fixtures(
        session,
        fixtures_envelopes=fixtures_envs,
        detail_batches=[
            FixtureDetailBatch(
                fixture_provider_id=1035055,
                players_envelope=players_env,
            ),
        ],
    )
    session.commit()
    assert result.counters.stats_corrected >= 1

    areola = session.execute(
        select(PlayerMatchStat).where(PlayerMatchStat.athlete_provider_id == 253),
    ).scalar_one()
    assert areola.minutes == 89
