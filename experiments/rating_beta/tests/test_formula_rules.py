"""Unit tests for Rating Beta (EP00-05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rating_beta import compute_rating, load_formula_config
from rating_beta.formula import round_to_step
from rating_beta.input import PlayerMatchInput, RelevantEvents

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = EXPERIMENT_ROOT / "config" / "beta-v0.1.yaml"


@pytest.fixture(scope="module")
def config():
    return load_formula_config(CONFIG)


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


# ---------------------------------------------------------------------------
# Config / version
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Minutes threshold + relevant events
# ---------------------------------------------------------------------------


def test_under_threshold_without_event_no_display(config):
    r = compute_rating(
        _player(minutes=10, position="F", relevant_events=RelevantEvents()),
        config,
    )
    assert r.eligible is False
    assert r.display is None
    assert r.eligibility_reason == "under_threshold_no_relevant_event"
    assert r.raw is not None  # raw still computed for diagnostics


def test_under_threshold_with_goal_is_eligible(config):
    r = compute_rating(
        _player(
            minutes=8,
            position="F",
            statistics={"goals": {"total": 1}, "shots": {"on": 1, "total": 1}},
            relevant_events=RelevantEvents(goal=True),
        ),
        config,
    )
    assert r.eligible is True
    assert r.eligibility_reason == "relevant_event_under_threshold"
    assert r.display is not None


def test_under_threshold_with_assist_is_eligible(config):
    r = compute_rating(
        _player(
            minutes=5,
            position="M",
            relevant_events=RelevantEvents(assist=True),
        ),
        config,
    )
    assert r.eligible is True
    assert r.display is not None


def test_zero_minutes_without_event_ineligible(config):
    r = compute_rating(_player(minutes=None, position="D"), config)
    assert r.eligible is False
    assert r.display is None
    assert r.eligibility_reason == "no_minutes"


def test_goalkeeper_starter_eligible_below_threshold(config):
    r = compute_rating(
        _player(
            position="G",
            minutes=10,
            substitute=False,
            statistics={"goals": {"saves": 1}},
        ),
        config,
    )
    assert r.eligible is True
    assert r.eligibility_reason == "goalkeeper_starter"
    assert r.role == "P"


def test_goalkeeper_substitute_still_needs_threshold_or_event(config):
    r = compute_rating(
        _player(position="G", minutes=10, substitute=True),
        config,
    )
    assert r.eligible is False
    assert r.eligibility_reason == "under_threshold_no_relevant_event"


# ---------------------------------------------------------------------------
# Clamp 3–10 and rounding to 0.5
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (6.0, 6.0),
        (6.24, 6.0),
        (6.25, 6.5),
        (6.74, 6.5),
        (6.75, 7.0),
        (7.1, 7.0),
        (3.0, 3.0),
        (10.0, 10.0),
    ],
)
def test_round_to_half(value, expected):
    assert round_to_step(value, 0.5) == expected


def test_clamp_upper_bound(config):
    # Extreme attacker stats should clamp at 10
    r = compute_rating(
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
    assert r.raw_before_clamp > 10
    assert r.raw == 10.0
    assert r.display == 10.0


def test_clamp_lower_bound(config):
    from rating_beta.config import ComponentSpec, FormulaConfig

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
    r = compute_rating(
        _player(
            position="F",
            minutes=90,
            statistics={"fouls": {"committed": 10}},
        ),
        harsh,
    )
    assert r.raw_before_clamp < 3
    assert r.raw == 3.0
    assert r.display == 3.0


def test_raw_preserved_display_rounded(config):
    r = compute_rating(
        _player(
            position="M",
            minutes=90,
            statistics={
                "passes": {"key": 1, "accuracy": "10", "total": 20},
                "tackles": {"total": 0},
                "dribbles": {"success": 0},
                "shots": {"on": 0},
                "fouls": {"committed": 0},
            },
        ),
        config,
    )
    assert r.raw != r.display or r.raw == r.display
    assert abs(r.display * 2 - round(r.display * 2)) < 1e-9
    assert r.reconstruct_with(config) == pytest.approx(r.raw)


# ---------------------------------------------------------------------------
# No double reward for goals / assists
# ---------------------------------------------------------------------------


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
    assert all(c.path not in config.excluded_stat_paths for c in with_ga.components)
    assert with_ga.goals_total == 3
    assert with_ga.assists_total == 2


def test_excluded_paths_never_used_as_components(config):
    for role, comps in config.roles.items():
        for c in comps:
            assert c.path not in config.excluded_stat_paths, f"{role}.{c.id}"


# ---------------------------------------------------------------------------
# Reconstructibility
# ---------------------------------------------------------------------------


def test_vote_reconstructible_from_components(config):
    r = compute_rating(
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
    rebuilt = r.base + sum(c.contribution for c in r.components)
    assert rebuilt == pytest.approx(r.raw_before_clamp)
    assert r.reconstruct_with(config) == pytest.approx(r.raw)
