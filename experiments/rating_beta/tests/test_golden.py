"""Golden tests on a fixed subset of the EP00-02 offline corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rating_beta import compute_rating, load_formula_config
from rating_beta.input import iter_players_from_payload, own_goal_player_ids_from_events

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
CONFIG = EXPERIMENT_ROOT / "config" / "beta-v0.1.yaml"
CORPUS = REPO / "backend" / "tests" / "fixtures" / "api_football" / "matches"

# Fixed golden subset: (league_id, fixture_id, player_id) → expected display / eligibility
GOLDEN = [
    # GK starter, 90' — Areola (penalty saved, saves)
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 253,
        "role": "P",
        "eligible": True,
        "display": 6.5,
        "raw": 6.732,
    },
    # Defender Emerson — strong tackle/duel profile
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 2284,
        "role": "D",
        "eligible": True,
        "display": 7.5,
        "raw": 7.732,
    },
    # Midfielder Ward-Prowse — 2 assists must NOT inflate statistical vote vs components
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
    # Forward Antonio — 1 goal excluded from formula
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
    # Sub Fornals 14' no relevant event → senza voto
    {
        "league_id": 39,
        "fixture_id": 1035055,
        "player_id": 1697,
        "role": "C",
        "eligible": False,
        "display": None,
    },
    # Sub Madueke exactly 15' → eleggibile
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
    return load_formula_config(CONFIG)


def _load_player(league_id: int, fixture_id: int, player_id: int):
    base = CORPUS / str(league_id) / str(fixture_id)
    players = json.loads((base / "fixtures_players.json").read_text(encoding="utf-8"))
    events = json.loads((base / "fixtures_events.json").read_text(encoding="utf-8"))
    own_goals = own_goal_player_ids_from_events(events)
    for p in iter_players_from_payload(
        fixture_id=fixture_id, players_payload=players, own_goal_player_ids=own_goals
    ):
        if p.player_id == player_id:
            return p
    raise AssertionError(f"player {player_id} not found in fixture {fixture_id}")


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: f"{c['fixture_id']}-{c['player_id']}")
def test_golden_subset(config, case):
    player = _load_player(case["league_id"], case["fixture_id"], case["player_id"])
    result = compute_rating(player, config)

    assert result.formula_version == "beta-v0.1"
    assert result.role == case["role"]
    assert result.eligible is case["eligible"]
    assert result.display == case["display"]

    if case.get("raw") is not None:
        assert result.raw == pytest.approx(case["raw"], abs=1e-3)
        assert result.reconstruct_with(config) == pytest.approx(result.raw)

    if "goals_total" in case:
        assert result.goals_total == case["goals_total"]
    if "assists_total" in case:
        assert result.assists_total == case["assists_total"]

    # Goals/assists never appear as formula components
    assert all(c.path not in ("goals.total", "goals.assists") for c in result.components)
