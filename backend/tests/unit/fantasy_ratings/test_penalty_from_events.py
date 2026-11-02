"""Il malus del rigore sbagliato non deve dipendere solo da stats_json.penalty."""

from __future__ import annotations

from types import SimpleNamespace

from fantasy_ratings.bonus import compute_bonus_malus
from fantasy_ratings.bonus_config import default_bonus_config
from fantasy_ratings.mapping import bonus_input_from_stat, penalty_counts_by_provider_id
from sports_data.normalization.types import ScoringEventKind

KANE = 184


def _event(kind: ScoringEventKind, athlete_provider_id: int, *, active: bool = True):
    return SimpleNamespace(
        is_active=active,
        scoring_kind=kind.value,
        athlete_provider_id=athlete_provider_id,
    )


def _stat(stats_json: dict, athlete_provider_id: int = KANE):
    return SimpleNamespace(
        stats_json=stats_json,
        athlete_provider_id=athlete_provider_id,
        club_id=None,
    )


def _fixture():
    return SimpleNamespace(home_club_id=None, away_club_id=None, home_goals=None, away_goals=None)


def _bonus_total(stat, events):
    missed, saved = penalty_counts_by_provider_id(events)
    bonus_input = bonus_input_from_stat(
        fixture=_fixture(),
        stat=stat,
        role="A",
        own_goal_counts={},
        penalty_missed_counts=missed,
        penalty_saved_counts=saved,
    )
    return compute_bonus_malus(bonus_input, default_bonus_config(), eligible=True), bonus_input


def test_missed_penalty_event_applies_malus_when_stats_lack_it():
    stat = _stat({"goals": {"total": 0}, "penalty": {}})
    result, bonus_input = _bonus_total(stat, [_event(ScoringEventKind.PENALTY_MISSED, KANE)])
    assert bonus_input.penalty_missed == 1
    assert result.total == -3.0


def test_off_target_penalty_counts_as_missed():
    stat = _stat({"penalty": {}})
    _, bonus_input = _bonus_total(stat, [_event(ScoringEventKind.PENALTY_OFF_TARGET, KANE)])
    assert bonus_input.penalty_missed == 1


def test_stats_and_event_for_same_penalty_are_not_summed():
    stat = _stat({"penalty": {"missed": 1}})
    result, bonus_input = _bonus_total(stat, [_event(ScoringEventKind.PENALTY_MISSED, KANE)])
    assert bonus_input.penalty_missed == 1
    assert result.total == -3.0


def test_inactive_events_and_other_players_are_ignored():
    stat = _stat({"penalty": {}})
    events = [
        _event(ScoringEventKind.PENALTY_MISSED, KANE, active=False),
        _event(ScoringEventKind.PENALTY_MISSED, 999),
    ]
    _, bonus_input = _bonus_total(stat, events)
    assert bonus_input.penalty_missed == 0
