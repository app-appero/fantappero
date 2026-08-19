"""Unit tests for fixture/event/lineup/stats mapping (EP04-05)."""

from __future__ import annotations

import json
from pathlib import Path

from sports_data.normalization.keys import event_provider_key
from sports_data.provider.envelope import parse_envelope
from sports_data.provider.mapping import (
    map_fixtures,
    map_match_events,
    map_official_lineups,
    map_player_match_stats,
)

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
MATCH = DATASET / "matches" / "39" / "1035055"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_map_fixtures_includes_round_and_status_elapsed() -> None:
    envelope = parse_envelope(_load(MATCH / "fixtures.json"), endpoint="/fixtures")
    rows = map_fixtures(envelope)
    assert len(rows) == 1
    fx = rows[0]
    assert fx.provider_id == 1035055
    assert fx.competition_provider_id == 39
    assert fx.season_year == 2023
    assert fx.home_club_provider_id == 48
    assert fx.away_club_provider_id == 49
    assert fx.status_short == "FT"
    assert fx.status_elapsed == 90
    assert fx.home_goals == 3
    assert fx.away_goals == 1
    assert fx.round_label == "Regular Season - 2"
    assert fx.home_club_name == "West Ham"


def test_map_match_events_idempotent_keys() -> None:
    envelope = parse_envelope(_load(MATCH / "fixtures_events.json"), endpoint="/fixtures/events")
    first = map_match_events(envelope, fixture_provider_id=1035055)
    second = map_match_events(envelope, fixture_provider_id=1035055)
    assert len(first) == 19
    assert [e.provider_event_key for e in first] == [e.provider_event_key for e in second]
    assert len({e.provider_event_key for e in first}) == len(first)
    goal = next(
        e
        for e in first
        if e.event_detail == "Normal Goal" and e.athlete_provider_id == 21694
    )
    assert goal.provider_event_key == event_provider_key(
        fixture_id=1035055,
        elapsed=7,
        extra=None,
        type_="Goal",
        detail="Normal Goal",
        player_id=21694,
        assist_id=2938,
        role="primary",
    )


def test_map_official_lineups_starters_and_subs() -> None:
    envelope = parse_envelope(_load(MATCH / "fixtures_lineups.json"), endpoint="/fixtures/lineups")
    lineups = map_official_lineups(envelope, fixture_provider_id=1035055)
    assert len(lineups) == 2
    west_ham = next(row for row in lineups if row.club_provider_id == 48)
    assert west_ham.formation == "4-2-3-1"
    starters = [e for e in west_ham.entries if e.is_starter]
    subs = [e for e in west_ham.entries if not e.is_starter]
    assert len(starters) == 11
    assert len(subs) == 9
    areola = next(e for e in starters if e.athlete_provider_id == 253)
    assert areola.position_raw == "G"
    assert areola.shirt_number == 23


def test_map_player_match_stats_minutes_and_hash() -> None:
    envelope = parse_envelope(_load(MATCH / "fixtures_players.json"), endpoint="/fixtures/players")
    stats = map_player_match_stats(envelope, fixture_provider_id=1035055)
    assert len(stats) >= 20
    areola = next(s for s in stats if s.athlete_provider_id == 253)
    assert areola.minutes == 90
    assert areola.position_raw == "G"
    assert areola.is_substitute is False
    assert areola.provider_rating == "7.9"
    assert areola.stats_hash
    assert areola.club_provider_id == 48
    # Idempotent hash on same payload
    again = map_player_match_stats(envelope, fixture_provider_id=1035055)
    assert [s.stats_hash for s in stats] == [s.stats_hash for s in again]
