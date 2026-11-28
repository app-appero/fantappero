"""Gol annullati dal VAR: abbinamento prudente tra evento ``Var`` e ``Goal`` (QA 28/11)."""

from __future__ import annotations

from sports_data.normalization import ScoringEventKind, normalize_scoring_events
from sports_data.normalization.disallowed import (
    disallowed_goal_indexes,
    without_disallowed_goals,
)

VENEZIA = 517
BOLOGNA = 500


def _row(type_: str, detail: str, minute: int, player: int | None, team: int | None, assist=None):
    return {
        "type": type_,
        "detail": detail,
        "player": {"id": player, "name": None},
        "assist": {"id": assist, "name": None},
        "team": {"id": team, "name": None},
        "time": {"elapsed": minute, "extra": None},
        "comments": None,
    }


def _goal(minute: int, player: int, team: int, *, assist: int | None = None, detail="Normal Goal"):
    return _row("Goal", detail, minute, player, team, assist)


def _var(minute: int, player: int | None, team: int | None, detail="Goal Disallowed - offside"):
    return _row("Var", detail, minute, player, team)


def test_var_disallowed_matches_goal_by_player():
    events = [
        _goal(15, 11, VENEZIA, assist=22),
        _row("Card", "Yellow Card", 15, 33, BOLOGNA),
        _var(15, 11, VENEZIA),
    ]
    assert disallowed_goal_indexes(events) == {0}
    assert [e["type"] for e in without_disallowed_goals(events)] == ["Card", "Var"]


def test_var_disallowed_falls_back_to_team_when_player_differs():
    events = [_goal(15, 11, VENEZIA, assist=22), _var(16, 99, VENEZIA)]
    assert disallowed_goal_indexes(events) == {0}


def test_var_disallowed_ignores_other_team_goals_and_goals_outside_window():
    events = [
        _goal(10, 11, VENEZIA),
        _goal(30, 12, BOLOGNA),
        _var(31, 99, VENEZIA),  # nessun gol del Venezia tra il 26' e il 31'
        _var(29, 12, BOLOGNA),  # il VAR non annulla un gol venuto dopo
    ]
    assert disallowed_goal_indexes(events) == set()


def test_var_disallowed_picks_goal_closest_before_var():
    events = [_goal(40, 11, VENEZIA), _goal(43, 12, VENEZIA), _var(44, None, VENEZIA)]
    assert disallowed_goal_indexes(events) == {1}


def test_goal_confirmed_after_cancel_restores_goal():
    events = [
        _goal(15, 11, VENEZIA),
        _var(15, 11, VENEZIA, detail="Goal cancelled"),
        _var(17, 11, VENEZIA, detail="Goal confirmed"),
    ]
    assert disallowed_goal_indexes(events) == set()


def test_penalty_confirmed_and_other_var_do_not_cancel_goals():
    events = [
        _goal(68, 11, VENEZIA, detail="Penalty"),
        _var(68, 11, VENEZIA, detail="Penalty confirmed"),
        _var(69, 11, VENEZIA, detail="Card upgrade"),
    ]
    assert disallowed_goal_indexes(events) == set()


def test_normalization_drops_goal_and_assist_of_disallowed_goal():
    payload = {
        "response": [
            _goal(15, 11, VENEZIA, assist=22),
            _var(15, 11, VENEZIA),
            _goal(60, 13, BOLOGNA, assist=14),
        ]
    }
    result = normalize_scoring_events(fixture_id=1, events_payload=payload, players_payload=None)
    pairs = {(e.kind, e.player_id) for e in result.events}
    assert pairs == {(ScoringEventKind.GOAL, 13), (ScoringEventKind.ASSIST, 14)}
