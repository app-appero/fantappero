"""Unit tests for statistical rating rules (EP07-01)."""

from __future__ import annotations

import pytest

from fantasy_ratings.config import ComponentSpec, FormulaConfig, default_formula_config
from fantasy_ratings.formula import compute_rating, round_to_step
from fantasy_ratings.input import PlayerMatchInput, RelevantEvents


@pytest.fixture(scope="module")
def config():
    return default_formula_config()


def _player(**kwargs) -> PlayerMatchInput:
    base = dict(
        fixture_id=1,
        player_id=100,
        player_name="Test Player",
        team_id=1,
        position="M",
        minutes=90,
        substitute=False,
        provider_rating=6.5,
        statistics={},
        relevant_events=RelevantEvents(),
    )
    base.update(kwargs)
    return PlayerMatchInput(**base)


def test_config_is_versioned(config):
    assert config.version == "beta-v0.1"
    assert config.base == 6.0
    assert config.clamp_min == 3.0
    assert config.clamp_max == 10.0
    assert config.display_step == 0.5
    assert config.minutes_threshold == 15
    assert set(config.roles) == {"P", "D", "C", "A"}
    assert "goals.total" in config.excluded_stat_paths
    assert "goals.assists" in config.excluded_stat_paths


def test_under_threshold_without_event_no_display(config):
    result = compute_rating(
        _player(minutes=10, position="F", relevant_events=RelevantEvents()),
        config,
    )
    assert result.eligible is False
    assert result.display is None
    assert result.eligibility_reason == "under_threshold_no_relevant_event"


def test_stoppage_entry_without_event_no_display(config):
    result = compute_rating(
        _player(
            minutes=2,
            position="M",
            substitute=True,
            entered_in_stoppage=True,
            relevant_events=RelevantEvents(),
        ),
        config,
    )
    assert result.eligible is False
    assert result.display is None
    assert result.eligibility_reason == "stoppage_entry_no_relevant_event"


def test_under_threshold_with_goal_is_eligible(config):
    result = compute_rating(
        _player(
            minutes=8,
            position="F",
            statistics={"goals": {"total": 1}, "shots": {"on": 1, "total": 1}},
            relevant_events=RelevantEvents(goal=True),
        ),
        config,
    )
    assert result.eligible is True
    assert result.display is not None


def test_goalkeeper_starter_eligible_below_threshold(config):
    result = compute_rating(
        _player(
            position="G",
            minutes=10,
            substitute=False,
            statistics={"goals": {"saves": 1}},
        ),
        config,
    )
    assert result.eligible is True
    assert result.eligibility_reason == "goalkeeper_starter"
    assert result.role == "P"


@pytest.mark.parametrize(
    "value,expected",
    [
        (6.0, 6.0),
        (6.24, 6.0),
        (6.25, 6.5),
        (6.74, 6.5),
        (6.75, 7.0),
    ],
)
def test_round_to_half(value, expected):
    assert round_to_step(value, 0.5) == expected


def test_clamp_upper_bound(config):
    result = compute_rating(
        _player(
            position="F",
            minutes=90,
            statistics={
                "shots": {"on": 20, "total": 30},
                "passes": {"key": 20},
                "dribbles": {"success": 20},
                "duels": {"won": 20},
                "fouls": {"committed": 0},
            },
        ),
        config,
    )
    assert result.raw_before_clamp > 10
    assert result.raw == 10.0
    assert result.display == 10.0


def test_clamp_lower_bound(config):
    harsh = FormulaConfig(
        version=config.version,
        card=config.card,
        base=config.base,
        clamp_min=config.clamp_min,
        clamp_max=config.clamp_max,
        display_step=config.display_step,
        minutes_threshold=config.minutes_threshold,
        goalkeeper_starter_always_eligible=config.goalkeeper_starter_always_eligible,
        relevant_event_flags=config.relevant_event_flags,
        excluded_stat_paths=config.excluded_stat_paths,
        position_map=config.position_map,
        roles={
            **config.roles,
            "A": (
                ComponentSpec(
                    id="fouls_committed",
                    path="fouls.committed",
                    coeff=-1.0,
                    max_abs=5.0,
                    transform="raw",
                ),
            ),
        },
    )
    result = compute_rating(
        _player(
            position="F",
            minutes=90,
            statistics={"fouls": {"committed": 10}},
        ),
        harsh,
    )
    assert result.raw_before_clamp < 3
    assert result.raw == 3.0
    assert result.display == 3.0


def test_goals_and_assists_do_not_change_statistical_vote(config):
    stats_base = {
        "passes": {"key": 2, "accuracy": "15", "total": 30},
        "tackles": {"total": 1},
        "dribbles": {"success": 1},
        "shots": {"on": 1},
        "fouls": {"committed": 0},
    }
    without = compute_rating(
        _player(
            position="M",
            statistics={**stats_base, "goals": {"total": 0, "assists": 0}},
        ),
        config,
    )
    with_ga = compute_rating(
        _player(
            position="M",
            statistics={**stats_base, "goals": {"total": 3, "assists": 2}},
            relevant_events=RelevantEvents(goal=True, assist=True),
        ),
        config,
    )
    assert without.raw == pytest.approx(with_ga.raw)
    assert without.display == with_ga.display
    assert all(item.path not in config.excluded_stat_paths for item in with_ga.components)


def test_vote_reconstructible_from_components(config):
    result = compute_rating(
        _player(
            position="D",
            minutes=90,
            statistics={
                "tackles": {"total": 4, "interceptions": 2, "blocks": 1},
                "duels": {"won": 5},
                "passes": {"accuracy": "40", "total": 50},
                "fouls": {"committed": 1},
            },
        ),
        config,
    )
    rebuilt = result.base + sum(item.contribution for item in result.components)
    assert rebuilt == pytest.approx(result.raw_before_clamp)
    assert result.reconstruct_with(config) == pytest.approx(result.raw)
