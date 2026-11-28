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
    related: int | None = None,
):
    return SimpleNamespace(
        is_active=active,
        scoring_kind=None if kind is None else kind.value,
        athlete_provider_id=pid,
        status=status,
        event_type=event_type,
        event_detail=detail,
        related_athlete_provider_id=related,
    )


def _card(detail: str, **kwargs):
    return _event(None, event_type="Card", detail=detail, status="timeline", **kwargs)


def _run(stats_json: dict, events: list, *, role: str = "A"):
    stat = SimpleNamespace(stats_json=stats_json, athlete_provider_id=PLAYER, club_id=None)
    fixture = SimpleNamespace(
        home_club_id=None, away_club_id=None, home_goals=None, away_goals=None
    )
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


# --- righe grezze della cronologia -------------------------------------------


def _timeline(detail: str, *, pid: int = PLAYER, related: int | None = None):
    return _event(
        None, pid=pid, status="timeline", event_type="Goal", detail=detail, related=related
    )


def test_timeline_missed_penalty_gives_malus_without_normalized_row():
    # "H. Kane — rigore sbagliato" in Cronologia, ma nessuna riga normalizzata.
    data, result = _run({"penalty": {}}, [_timeline("Missed Penalty")])
    assert data.penalty_missed == 1
    assert result.total == -3.0


def test_timeline_and_normalized_missed_penalty_are_not_summed():
    events = [
        _timeline("Missed Penalty"),
        _event(ScoringEventKind.PENALTY_MISSED, detail="Missed Penalty"),
    ]
    data, _ = _run({"penalty": {"missed": 1}}, events)
    assert data.penalty_missed == 1


def test_timeline_goal_and_assist_give_bonus_to_scorer_and_assister():
    events = [_timeline("Normal Goal", pid=1, related=PLAYER)]
    data, result = _run({}, events)
    assert (data.goals, data.assists) == (0, 1)
    assert result.total == 1.0
    scorer = _run_for(1, events)
    assert scorer.goals == 1


def test_timeline_var_cancelled_goal_and_own_goal_do_not_count_as_goal():
    events = [
        _event(None, status="timeline", event_type="Var", detail="Goal cancelled"),
        _timeline("Own Goal"),
    ]
    data, _ = _run({}, events)
    assert data.goals == 0


def _run_for(pid: int, events: list):
    stat = SimpleNamespace(stats_json={}, athlete_provider_id=pid, club_id=None)
    fixture = SimpleNamespace(
        home_club_id=None, away_club_id=None, home_goals=None, away_goals=None
    )
    return bonus_input_from_stat(
        fixture=fixture,
        stat=stat,
        role="A",
        own_goal_counts={},
        event_counts=event_bonus_counts(events),
    )


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


# --- partita finita: niente piu' gol/assist di quelli della squadra (QA 28/11) ---

HOME = "home-club"
AWAY = "away-club"


def _run_final(stats_json: dict, events: list, *, status: str, home: int | None, away: int | None):
    stat = SimpleNamespace(stats_json=stats_json, athlete_provider_id=PLAYER, club_id=HOME)
    fixture = SimpleNamespace(
        home_club_id=HOME,
        away_club_id=AWAY,
        home_goals=home,
        away_goals=away,
        status_short=status,
    )
    data = bonus_input_from_stat(
        fixture=fixture,
        stat=stat,
        role="C",
        own_goal_counts={},
        event_counts=event_bonus_counts(events),
    )
    return data, compute_bonus_malus(data, default_bonus_config(), eligible=True)


def test_finished_nil_nil_gives_no_goal_or_assist_even_with_stale_data():
    """Venezia–Bologna 0-0: assist rimasto nelle statistiche o negli eventi dopo il VAR."""
    events = [_event(ScoringEventKind.ASSIST), _event(ScoringEventKind.GOAL)]
    data, result = _run_final(
        {"goals": {"total": 1, "assists": 1}}, events, status="FT", home=0, away=0
    )
    assert (data.goals, data.assists) == (0, 0)
    assert {c.id for c in result.components} == set()


def test_finished_match_caps_at_team_goals_not_below():
    data, _ = _run_final({"goals": {"total": 3, "assists": 2}}, [], status="AET", home=2, away=0)
    assert (data.goals, data.assists) == (2, 2)


def test_live_match_is_not_capped_by_lagging_score():
    data, _ = _run_final({"goals": {"total": 1, "assists": 1}}, [], status="2H", home=0, away=0)
    assert (data.goals, data.assists) == (1, 1)


def test_finished_match_without_score_is_not_capped():
    data, _ = _run_final({"goals": {"total": 1}}, [], status="FT", home=None, away=None)
    assert data.goals == 1
