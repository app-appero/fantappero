"""Golden tests on the EP00-02 offline corpus (EP07-01)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fantasy_ratings.config import default_formula_config
from fantasy_ratings.formula import compute_rating
from fantasy_ratings.input import (
    iter_players_from_payload,
    own_goal_player_ids_from_events,
    stoppage_entry_ids_from_events,
)

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "tests" / "fixtures" / "api_football" / "matches"

GOLDEN = [
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 253,
        "role": "P",
        "eligible": True,
        "display": 6.5,
        "raw": 6.732,
    },
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 2284,
        "role": "D",
        "eligible": True,
        "display": 7.5,
        "raw": 7.732,
    },
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 2938,
        "role": "C",
        "eligible": True,
        "display": 7.5,
        "raw": 7.342,
        "assists_total": 2,
    },
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 18819,
        "role": "A",
        "eligible": True,
        "display": 6.5,
        "raw": 6.38,
        "goals_total": 1,
    },
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 1697,
        "role": "C",
        "eligible": False,
        "display": None,
        "eligibility_reason": "under_threshold_no_relevant_event",
    },
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 136723,
        "role": "A",
        "eligible": True,
        "display": 6.5,
        "raw": 6.33,
    },
]


@pytest.fixture(scope="module")
def config():
    return default_formula_config()


def _load_player(league_id: int, fixture_id: int, player_id: int):
    base = CORPUS / str(league_id) / str(fixture_id)
    players = json.loads((base / "fixtures_players.json").read_text(encoding="utf-8"))
    events = json.loads((base / "fixtures_events.json").read_text(encoding="utf-8"))
    own_goals = own_goal_player_ids_from_events(events)
    stoppage_ids = stoppage_entry_ids_from_events(events)
    for player in iter_players_from_payload(
        fixture_id=fixture_id,
        players_payload=players,
        own_goal_player_ids=own_goals,
        stoppage_entry_player_ids=stoppage_ids,
    ):
        if player.player_id == player_id:
            return player
    raise AssertionError(f"player {player_id} not found in fixture {fixture_id}")


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: f"{c['fixture_id']}-{c['player_id']}")
def test_golden_subset(config, case):
    player = _load_player(case["league_id"], case["fixture_id"], case["player_id"])
    result = compute_rating(player, config)

    assert result.formula_version == "beta-v0.1"
    assert result.role == case["role"]
    assert result.eligible is case["eligible"]
    assert result.display == case["display"]
    if "eligibility_reason" in case:
        assert result.eligibility_reason == case["eligibility_reason"]
    assert player.entered_in_stoppage is False

    if case.get("raw") is not None:
        assert result.raw == pytest.approx(case["raw"], abs=1e-3)
        assert result.reconstruct_with(config) == pytest.approx(result.raw)

    if "goals_total" in case:
        assert result.goals_total == case["goals_total"]
    if "assists_total" in case:
        assert result.assists_total == case["assists_total"]

    assert all(item.path not in ("goals.total", "goals.assists") for item in result.components)


def test_fornals_remains_senza_voto_on_spike_payload(config) -> None:
    player = _load_player(39, 1035055, 1697)
    result = compute_rating(player, config)
    assert player.minutes == 14
    assert player.entered_in_stoppage is False
    assert result.eligible is False
    assert result.display is None
    assert result.eligibility_reason == "under_threshold_no_relevant_event"


def test_madueke_ineligible_when_league_threshold_is_higher(config) -> None:
    player = _load_player(39, 1035055, 136723)
    assert player.minutes == 15
    raised = config.with_minutes_threshold(16)
    result = compute_rating(player, raised)
    assert result.eligible is False
    assert result.display is None
    assert result.eligibility_reason == "under_threshold_no_relevant_event"


def test_stoppage_entry_payload_without_event_is_senza_voto(config) -> None:
    events = {
        "response": [
            {
                "type": "subst",
                "player": {"id": 1, "name": "Starter"},
                "assist": {"id": 9001, "name": "Late Sub"},
                "time": {"elapsed": 90, "extra": 2},
            }
        ]
    }
    players = {
        "response": [
            {
                "team": {"id": 48},
                "players": [
                    {
                        "player": {"id": 9001, "name": "Late Sub"},
                        "statistics": [
                            {
                                "games": {
                                    "minutes": 2,
                                    "position": "M",
                                    "substitute": True,
                                    "rating": None,
                                },
                                "goals": {"total": 0, "assists": 0},
                                "penalty": {"missed": 0},
                                "cards": {"red": 0},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    stoppage_ids = stoppage_entry_ids_from_events(events)
    assert stoppage_ids == {9001}
    player = iter_players_from_payload(
        fixture_id=1035055,
        players_payload=players,
        stoppage_entry_player_ids=stoppage_ids,
    )[0]
    result = compute_rating(player, config)
    assert player.entered_in_stoppage is True
    assert result.eligible is False
    assert result.display is None
    assert result.eligibility_reason == "stoppage_entry_no_relevant_event"
