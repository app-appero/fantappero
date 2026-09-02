"""Parameterized tests for EP00-03 scoring-event normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sports_data.normalization import (
    AnomalyCode,
    EventStatus,
    ScoringEventKind,
    normalize_scoring_events,
)

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
MATCHES = DATASET / "matches"


def _load_fixture(league_id: int, fixture_id: int) -> tuple[dict, dict]:
    base = MATCHES / str(league_id) / str(fixture_id)
    events = json.loads((base / "fixtures_events.json").read_text(encoding="utf-8"))
    players = json.loads((base / "fixtures_players.json").read_text(encoding="utf-8"))
    return events, players


def _kinds(result) -> list[ScoringEventKind]:
    return [e.kind for e in result.events]


def _by_kind(result, kind: ScoringEventKind):
    return [e for e in result.events if e.kind == kind]


# ---------------------------------------------------------------------------
# Positive cases from frozen corpus (one per available scoring kind)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "league_id,fixture_id,kind,player_id",
    [
        (78, 1388315, ScoringEventKind.GOAL, 21393),  # Guirassy Normal Goal
        (78, 1388315, ScoringEventKind.PENALTY_SCORED, 1672),  # Sinani
        (78, 1388315, ScoringEventKind.ASSIST, 1159),  # Sabitzer
        (61, 718611, ScoringEventKind.OWN_GOAL, 1254),  # Poussin
        (140, 1038042, ScoringEventKind.PENALTY_MISSED, 2060),  # Munir (saved)
        (140, 1038042, ScoringEventKind.PENALTY_SAVED, 47527),  # Dimitrievski
    ],
)
def test_positive_event_kinds_from_corpus(league_id, fixture_id, kind, player_id):
    events, players = _load_fixture(league_id, fixture_id)
    result = normalize_scoring_events(
        fixture_id=fixture_id, events_payload=events, players_payload=players
    )
    matched = [e for e in _by_kind(result, kind) if e.player_id == player_id]
    assert matched, f"expected {kind} for player {player_id} in fixture {fixture_id}"
    assert matched[0].status in (EventStatus.CONFIRMED, EventStatus.PROVISIONAL)


def test_own_goal_not_counted_as_goal():
    events, players = _load_fixture(61, 718611)
    result = normalize_scoring_events(
        fixture_id=718611, events_payload=events, players_payload=players
    )
    assert any(e.kind == ScoringEventKind.OWN_GOAL and e.player_id == 1254 for e in result.events)
    assert not any(e.kind == ScoringEventKind.GOAL and e.player_id == 1254 for e in result.events)


def test_assist_not_duplicated_from_stats():
    events, players = _load_fixture(78, 1388315)
    result = normalize_scoring_events(
        fixture_id=1388315, events_payload=events, players_payload=players
    )
    assists = _by_kind(result, ScoringEventKind.ASSIST)
    assert len(assists) == 5
    assert all(e.sources == ("events",) for e in assists)
    assert AnomalyCode.ASSIST_COUNT_MISMATCH not in result.anomalies


def test_penalty_off_target_synthetic():
    """Corpus has no pure off-target; synthetic Missed Penalty without save."""
    events = {
        "response": [
            {
                "type": "Goal",
                "detail": "Missed Penalty",
                "player": {"id": 101, "name": "Taker"},
                "assist": {"id": None, "name": None},
                "team": {"id": 1, "name": "A"},
                "time": {"elapsed": 44, "extra": None},
                "comments": None,
            }
        ]
    }
    players = {
        "response": [
            {
                "team": {"id": 1},
                "players": [
                    {
                        "player": {"id": 101, "name": "Taker"},
                        "statistics": [
                            {
                                "goals": {"total": None, "assists": None},
                                "penalty": {
                                    "scored": 0,
                                    "missed": 1,
                                    "saved": 0,
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "team": {"id": 2},
                "players": [
                    {
                        "player": {"id": 201, "name": "GK"},
                        "statistics": [
                            {
                                "goals": {"total": None, "assists": None},
                                "penalty": {
                                    "scored": 0,
                                    "missed": 0,
                                    "saved": 0,
                                },
                            }
                        ],
                    }
                ],
            },
        ]
    }
    result = normalize_scoring_events(fixture_id=1, events_payload=events, players_payload=players)
    off = _by_kind(result, ScoringEventKind.PENALTY_OFF_TARGET)
    assert len(off) == 1
    assert off[0].player_id == 101
    assert off[0].status == EventStatus.CONFIRMED
    assert not _by_kind(result, ScoringEventKind.PENALTY_SAVED)


# ---------------------------------------------------------------------------
# Conflict / incomplete sources between endpoints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "league_id,fixture_id",
    [
        (39, 1035055),  # miss+save only in stats
        (78, 1388315),
        (61, 718611),
    ],
)
def test_stats_only_miss_save_is_provisional_not_silent(league_id, fixture_id):
    events, players = _load_fixture(league_id, fixture_id)
    result = normalize_scoring_events(
        fixture_id=fixture_id, events_payload=events, players_payload=players
    )
    assert AnomalyCode.EVENTS_MISSING_MISSED_PENALTY in result.anomalies
    saved = _by_kind(result, ScoringEventKind.PENALTY_SAVED)
    missed = _by_kind(result, ScoringEventKind.PENALTY_MISSED)
    assert saved
    assert missed
    assert all(e.status == EventStatus.PROVISIONAL for e in saved + missed)


def test_goal_count_mismatch_surfaces_anomaly():
    events = {
        "response": [
            {
                "type": "Goal",
                "detail": "Normal Goal",
                "player": {"id": 1, "name": "A"},
                "assist": {"id": None, "name": None},
                "team": {"id": 10},
                "time": {"elapsed": 10, "extra": None},
            }
        ]
    }
    players = {
        "response": [
            {
                "team": {"id": 10},
                "players": [
                    {
                        "player": {"id": 1},
                        "statistics": [
                            {
                                "goals": {"total": 2, "assists": 0},
                                "penalty": {"scored": 0, "missed": 0, "saved": 0},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    result = normalize_scoring_events(fixture_id=99, events_payload=events, players_payload=players)
    assert AnomalyCode.GOAL_COUNT_MISMATCH in result.anomalies
    assert AnomalyCode.STATS_ONLY_GOAL in result.anomalies
    # Still exactly one goal event from events — no silent invent from stats
    assert len(_by_kind(result, ScoringEventKind.GOAL)) == 1


def test_assist_mismatch_does_not_invent_assists():
    events = {
        "response": [
            {
                "type": "Goal",
                "detail": "Normal Goal",
                "player": {"id": 1, "name": "Scorer"},
                "assist": {"id": None, "name": None},
                "team": {"id": 10},
                "time": {"elapsed": 10, "extra": None},
            }
        ]
    }
    players = {
        "response": [
            {
                "team": {"id": 10},
                "players": [
                    {
                        "player": {"id": 2},
                        "statistics": [
                            {
                                "goals": {"total": 0, "assists": 1},
                                "penalty": {"scored": 0, "missed": 0, "saved": 0},
                            }
                        ],
                    },
                    {
                        "player": {"id": 1},
                        "statistics": [
                            {
                                "goals": {"total": 1, "assists": 0},
                                "penalty": {"scored": 0, "missed": 0, "saved": 0},
                            }
                        ],
                    },
                ],
            }
        ]
    }
    result = normalize_scoring_events(fixture_id=98, events_payload=events, players_payload=players)
    assert AnomalyCode.ASSIST_COUNT_MISMATCH in result.anomalies
    assert AnomalyCode.STATS_ONLY_ASSIST in result.anomalies
    assert _by_kind(result, ScoringEventKind.ASSIST) == []


def test_orphan_penalty_save_is_insufficient():
    events = {"response": []}
    players = {
        "response": [
            {
                "team": {"id": 2},
                "players": [
                    {
                        "player": {"id": 50, "name": "GK"},
                        "statistics": [
                            {
                                "goals": {"total": None, "assists": None},
                                "penalty": {"scored": 0, "missed": 0, "saved": 1},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    result = normalize_scoring_events(fixture_id=77, events_payload=events, players_payload=players)
    assert AnomalyCode.ORPHAN_PENALTY_SAVE in result.anomalies
    saved = _by_kind(result, ScoringEventKind.PENALTY_SAVED)
    assert len(saved) == 1
    assert saved[0].status == EventStatus.INSUFFICIENT


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "league_id,fixture_id",
    [
        (61, 718611),
        (140, 1038042),
        (78, 1388315),
        (39, 1035055),
    ],
)
def test_normalization_idempotent(league_id, fixture_id):
    events, players = _load_fixture(league_id, fixture_id)
    first = normalize_scoring_events(
        fixture_id=fixture_id, events_payload=events, players_payload=players
    )
    second = normalize_scoring_events(
        fixture_id=fixture_id, events_payload=events, players_payload=players
    )
    assert [e.as_dict() for e in first.events] == [e.as_dict() for e in second.events]
    assert first.anomalies == second.anomalies
    keys = [e.provider_event_key for e in first.events]
    assert len(keys) == len(set(keys)), "provider_event_key must be unique within fixture"


# ---------------------------------------------------------------------------
# Missing / unknown
# ---------------------------------------------------------------------------


def test_unknown_goal_detail():
    events = {
        "response": [
            {
                "type": "Goal",
                "detail": "Something Weird",
                "player": {"id": 9, "name": "X"},
                "assist": {"id": None, "name": None},
                "team": {"id": 1},
                "time": {"elapsed": 1, "extra": None},
            }
        ]
    }
    result = normalize_scoring_events(
        fixture_id=2, events_payload=events, players_payload={"response": []}
    )
    unknown = _by_kind(result, ScoringEventKind.UNKNOWN)
    assert len(unknown) == 1
    assert unknown[0].status == EventStatus.INSUFFICIENT
    assert AnomalyCode.UNKNOWN_GOAL_DETAIL in result.anomalies


def test_missing_player_id_on_goal():
    events = {
        "response": [
            {
                "type": "Goal",
                "detail": "Normal Goal",
                "player": {"id": None, "name": None},
                "assist": {"id": None, "name": None},
                "team": {"id": 1},
                "time": {"elapsed": 12, "extra": None},
            }
        ]
    }
    result = normalize_scoring_events(
        fixture_id=3, events_payload=events, players_payload={"response": []}
    )
    goals = _by_kind(result, ScoringEventKind.GOAL)
    assert len(goals) == 1
    assert goals[0].status == EventStatus.INSUFFICIENT
    assert AnomalyCode.MISSING_PLAYER_ID in goals[0].anomaly_codes


def test_empty_payloads():
    result = normalize_scoring_events(fixture_id=0, events_payload=None, players_payload=None)
    assert result.events == ()
    assert result.anomalies == ()


def test_confirmed_miss_save_when_event_present():
    events, players = _load_fixture(140, 1038042)
    result = normalize_scoring_events(
        fixture_id=1038042, events_payload=events, players_payload=players
    )
    missed = _by_kind(result, ScoringEventKind.PENALTY_MISSED)
    saved = _by_kind(result, ScoringEventKind.PENALTY_SAVED)
    assert len(missed) == 1 and missed[0].status == EventStatus.CONFIRMED
    assert len(saved) == 1 and saved[0].status == EventStatus.CONFIRMED
    assert AnomalyCode.EVENTS_MISSING_MISSED_PENALTY not in result.anomalies
