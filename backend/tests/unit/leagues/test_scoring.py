"""Unit tests for fantasy-goal conversion and H2H outcome (EP07-05 / FR-SCO-03)."""

from __future__ import annotations

import pytest

from leagues.scoring import (
    AWAY_WIN,
    DRAW,
    HOME_WIN,
    MatchOutcome,
    compare_fantasy_goals,
    fantasy_goals_for_points,
)


@pytest.mark.parametrize(
    ("points", "expected_goals"),
    [
        (0.0, 0),
        (65.0, 0),
        (65.5, 0),  # FR-SCO-03: confine 65,5 -> 0 gol
        (66.0, 1),  # confine 66 -> 1 gol
        (70.0, 1),
        (71.5, 1),  # confine 71,5 -> ancora 1 gol
        (72.0, 2),  # confine 72 -> 2 gol
        (77.5, 2),
        (78.0, 3),
        (84.0, 4),
        (108.0, 8),
    ],
)
def test_fantasy_goals_boundaries(points: float, expected_goals: int) -> None:
    assert fantasy_goals_for_points(points) == expected_goals


def test_compare_fantasy_goals() -> None:
    assert compare_fantasy_goals(2, 1) == HOME_WIN
    assert compare_fantasy_goals(1, 2) == AWAY_WIN
    assert compare_fantasy_goals(1, 1) == DRAW


def test_match_outcome_from_points_same_band_is_draw() -> None:
    """Decisione Beta sullo scarto minimo (FR-SCO-03 §Eccezioni): stessa fascia
    gol -> pareggio, anche se il punteggio grezzo differisce."""
    outcome = MatchOutcome.from_points(home_points=66.0, away_points=71.5)
    assert outcome.home_fantasy_goals == 1
    assert outcome.away_fantasy_goals == 1
    assert outcome.outcome == DRAW


def test_match_outcome_from_points_different_band() -> None:
    outcome = MatchOutcome.from_points(home_points=72.0, away_points=65.0)
    assert outcome.home_fantasy_goals == 2
    assert outcome.away_fantasy_goals == 0
    assert outcome.outcome == HOME_WIN


def test_recompute_is_deterministic() -> None:
    first = MatchOutcome.from_points(home_points=80.5, away_points=79.0)
    second = MatchOutcome.from_points(home_points=80.5, away_points=79.0)
    assert first == second
