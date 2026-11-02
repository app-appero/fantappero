"""Bonus/malus: statistiche e eventi sono due viste dello stesso fatto.

Se la statistica del provider manca o arriva in ritardo, l'evento della partita
deve comunque dare il bonus/malus; se ci sono entrambi si usa il valore piu'
alto, mai la somma.
"""

from __future__ import annotations

from types import SimpleNamespace

from fantasy_ratings.bonus import compute_bonus_malus
from fantasy_ratings.bonus_config import default_bonus_config
from fantasy_ratings.mapping import bonus_input_from_stat, event_bonus_counts
from sports_data.normalization.types import ScoringEventKind

PLAYER = 184


def _event(
    kind: ScoringEventKind | None = None,
    *,
    pid: int = PLAYER,
    active: bool = True,
    status: str = "confirmed",
    event_type: str = "Goal",
    detail: str | None = None,
):
    return SimpleNamespace(
        is_active=active,
        scoring_kind=None if kind is None else kind.value,
        athlete_provider_id=pid,
        status=status,
        event_type=event_type,
        event_detail=detail,
    )


def _card(detail: str, **kwargs):
    return _event(None, event_type="Card", detail=detail, status="timeline", **kwargs)


def _run(stats_json: dict, events: list, *, role: str = "A"):
    stat = SimpleNamespace(stats_json=stats_json, athlete_provider_id=PLAYER, club_id=None)
    fixture = SimpleNamespace(home_club_id=None, away_club_id=None, home_goals=None, away_goals=None)
    data = bonus_input_from_stat(
        fixture=fixture,
        stat=stat,
        role=role,
        own_goal_counts={},
        event_counts=event_bonus_counts(events),
    )
    return data, compute_bonus_malus(data, default_bonus_config(), eligible=True)


# --- rigori ---------------------------------------------------------------


def test_missed_penalty_event_applies_malus_when_stats_lack_it():
    data, result = _run({"penalty": {}}, [_event(ScoringEventKind.PENALTY_MISSED)])
    assert data.penalty_missed == 1
    assert result.total == -3.0


def test_off_target_penalty_counts_as_missed():
    data, _ = _run({"penalty": {}}, [_event(ScoringEventKind.PENALTY_OFF_TARGET)])
    assert data.penalty_missed == 1


def test_penalty_in_stats_and_event_is_not_summed():
    data, result = _run({"penalty": {"missed": 1}}, [_event(ScoringEventKind.PENALTY_MISSED)])
    assert data.penalty_missed == 1
    assert result.total == -3.0


def test_goalkeeper_saved_penalty_from_events():
    data, result = _run({"penalty": {}}, [_event(ScoringEventKind.PENALTY_SAVED)], role="P")
    assert data.penalty_saved == 1
    assert result.total == 3.0


# --- gol e assist ----------------------------------------------------------


def test_goal_event_gives_bonus_when_stats_lack_it():
    data, result = _run({"goals": {"total": 0}}, [_event(ScoringEventKind.GOAL)])
    assert data.goals == 1
    assert result.total == 3.0


def test_penalty_scored_event_counts_as_goal_once():
    data, _ = _run({"goals": {"total": 1}}, [_event(ScoringEventKind.PENALTY_SCORED)])
    assert data.goals == 1


def test_two_goal_events_beat_a_stale_stat_of_one():
    data, result = _run(
        {"goals": {"total": 1}},
        [_event(ScoringEventKind.GOAL), _event(ScoringEventKind.GOAL)],
    )
    assert data.goals == 2
    assert result.total == 6.0


def test_assist_event_gives_bonus_when_stats_lack_it():
    data, result = _run({"goals": {"assists": None}}, [_event(ScoringEventKind.ASSIST)])
    assert data.assists == 1
    assert result.total == 1.0


def test_assist_in_stats_and_event_is_not_summed():
    data, _ = _run({"goals": {"assists": 1}}, [_event(ScoringEventKind.ASSIST)])
    assert data.assists == 1


# --- cartellini ------------------------------------------------------------


def test_yellow_card_event_gives_malus_when_stats_lack_it():
    data, result = _run({"cards": {"yellow": 0}}, [_card("Yellow Card")])
    assert data.yellow_card is True
    assert result.total == -0.5


def test_red_card_event_gives_malus_and_supersedes_yellow():
    data, result = _run({}, [_card("Yellow Card"), _card("Red Card")])
    assert data.red_card is True
    assert result.total == -1.0


def test_second_yellow_event_counts_as_expulsion():
    data, result = _run({}, [_card("Second Yellow card")])
    assert data.red_card is True
    assert result.total == -1.0


# --- esclusioni ------------------------------------------------------------


def test_inactive_anomalous_and_other_players_events_are_ignored():
    events = [
        _event(ScoringEventKind.GOAL, active=False),
        _event(ScoringEventKind.GOAL, status="anomaly"),
        _event(ScoringEventKind.ASSIST, status="insufficient"),
        _event(ScoringEventKind.PENALTY_MISSED, pid=999),
        _card("Red Card", pid=999),
        _card("Yellow Card", active=False),
    ]
    data, result = _run({}, events)
    assert (data.goals, data.assists, data.penalty_missed) == (0, 0, 0)
    assert data.yellow_card is False and data.red_card is False
    assert result.total == 0.0
