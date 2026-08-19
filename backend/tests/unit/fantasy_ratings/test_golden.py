"""Golden tests on the EP00-02 offline corpus (EP07-01 / EP07-03)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fantasy_ratings.bonus import BonusMalusInput, compute_bonus_malus
from fantasy_ratings.bonus_config import default_bonus_config
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


# EP07-03 / FR-SCO-02: fixture 39/1035055 (West Ham 3-1 Chelsea, home club_id=48,
# away club_id=49). Ogni caso e' ricavato direttamente dalle statistiche reali
# del corpus offline (fixtures_players.json / fixtures_events.json).
BONUS_GOLDEN = [
    {
        # Areola (P, West Ham): 1 rigore parato, 1 gol subito, no clean sheet.
        "player_id": 253,
        "team_goals_conceded": 1,
        "components": {"penalty_saved": 3.0, "goalkeeper_goal_conceded": -1.0},
        "total": 2.0,
    },
    {
        # Emerson (D, West Ham): un solo cartellino giallo, nessun autogol.
        "player_id": 2284,
        "team_goals_conceded": 0,
        "components": {"yellow_card": -0.5},
        "total": -0.5,
    },
    {
        # Ward-Prowse (C, West Ham): 2 assist, nessun'altra penalita'.
        "player_id": 2938,
        "team_goals_conceded": 0,
        "components": {"assist": 2.0},
        "total": 2.0,
    },
    {
        # Antonio (A, West Ham): 1 gol.
        "player_id": 18819,
        "team_goals_conceded": 0,
        "components": {"goal": 3.0},
        "total": 3.0,
    },
    {
        # Aguerd (D, West Ham): 1 gol + doppia ammonizione/espulsione nello
        # stesso episodio al 67' -> solo il malus espulsione viene applicato.
        "player_id": 21694,
        "team_goals_conceded": 0,
        "components": {"goal": 3.0, "red_card": -1.0},
        "total": 2.0,
    },
    {
        # Paqueta (C, West Ham): rigore segnato (gia' incluso in goals.total,
        # nessun bonus aggiuntivo per "rigore segnato") + 1 cartellino giallo.
        "player_id": 1646,
        "team_goals_conceded": 0,
        "components": {"goal": 3.0, "yellow_card": -0.5},
        "total": 2.5,
    },
    {
        # Enzo Fernandez (C, Chelsea): 1 rigore sbagliato.
        "player_id": 5996,
        "team_goals_conceded": 3,
        "components": {"penalty_missed": -3.0},
        "total": -3.0,
    },
]


@pytest.fixture(scope="module")
def bonus_config():
    return default_bonus_config()


def _bonus_input_from_player(
    player, *, team_goals_conceded: int, role: str | None
) -> BonusMalusInput:
    stats = player.statistics
    cards = stats.get("cards") or {}
    penalty = stats.get("penalty") or {}
    return BonusMalusInput(
        goals=player.goals_total,
        assists=player.assists_total,
        yellow_card=int(cards.get("yellow") or 0) > 0,
        red_card=int(cards.get("red") or 0) > 0,
        penalty_missed=int(penalty.get("missed") or 0),
        penalty_saved=int(penalty.get("saved") or 0),
        role=role,
        team_goals_conceded=team_goals_conceded,
    )


@pytest.mark.parametrize("case", BONUS_GOLDEN, ids=lambda c: str(c["player_id"]))
def test_bonus_malus_golden_subset(config, bonus_config, case):
    player = _load_player(39, 1035055, case["player_id"])
    rating = compute_rating(player, config)
    assert rating.eligible is True

    bonus_input = _bonus_input_from_player(
        player,
        team_goals_conceded=case["team_goals_conceded"],
        role=rating.role,
    )
    result = compute_bonus_malus(bonus_input, bonus_config, eligible=rating.eligible)

    actual = {item.id: item.contribution for item in result.components}
    assert actual == case["components"]
    assert result.total == pytest.approx(case["total"])

    fantasy_score = round(rating.display + result.total, 10)
    assert fantasy_score == pytest.approx(rating.display + case["total"])
