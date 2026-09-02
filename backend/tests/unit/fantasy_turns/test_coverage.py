"""Unit tests for the lineup-coverage turn validity engine."""

from __future__ import annotations

from database.enums import FantasyRole
from fantasy_turns.coverage import (
    DEFAULT_COVERAGE_THRESHOLD,
    coverage_threshold_for,
    lineup_coverage,
    window_is_valid,
)


def test_full_squad_covers_the_whole_lineup() -> None:
    available = {FantasyRole.P: 1, FantasyRole.D: 5, FantasyRole.C: 5, FantasyRole.A: 3}
    assert lineup_coverage(available) == 1.0


def test_empty_roster_covers_nothing() -> None:
    assert lineup_coverage({}) == 0.0


def test_coverage_uses_the_best_module_not_a_fixed_one() -> None:
    # 3 difensori / 5 centrocampisti / 2 attaccanti: il 3-5-2 copre tutto,
    # un modulo fisso come il 4-4-2 lascerebbe uno slot scoperto.
    available = {FantasyRole.P: 1, FantasyRole.D: 3, FantasyRole.C: 5, FantasyRole.A: 2}
    assert lineup_coverage(available) == 1.0


def test_missing_goalkeeper_costs_exactly_one_slot() -> None:
    available = {FantasyRole.P: 0, FantasyRole.D: 5, FantasyRole.C: 5, FantasyRole.A: 3}
    assert lineup_coverage(available) == 10 / 11


def test_extra_players_in_one_role_do_not_inflate_coverage() -> None:
    # 11 attaccanti non permettono comunque di schierare una formazione:
    # il modulo con più attaccanti ne accetta 3, più il portiere mancante.
    available = {FantasyRole.A: 11}
    assert lineup_coverage(available) == 3 / 11


def test_second_goalkeeper_does_not_count_twice() -> None:
    one = {FantasyRole.P: 1, FantasyRole.D: 4, FantasyRole.C: 4, FantasyRole.A: 2}
    two = {FantasyRole.P: 2, FantasyRole.D: 4, FantasyRole.C: 4, FantasyRole.A: 2}
    assert lineup_coverage(one) == lineup_coverage(two) == 1.0


def test_partial_squad_is_a_fraction_of_eleven() -> None:
    available = {FantasyRole.P: 1, FantasyRole.D: 3, FantasyRole.C: 3, FantasyRole.A: 1}
    # 3-4-3 → 3 dif + 3 cen + 1 att = 7 di movimento, più il portiere.
    assert lineup_coverage(available) == 8 / 11


def test_window_needs_every_team_above_threshold() -> None:
    assert window_is_valid([0.8, 0.9, 1.0], 0.75) is True
    assert window_is_valid([0.8, 0.7, 1.0], 0.75) is False


def test_window_without_any_roster_is_never_valid() -> None:
    """Niente turni prima dell'asta: nessuna rosa, nessun turno."""
    assert window_is_valid([], 0.75) is False


def test_threshold_falls_back_to_the_default_when_unset() -> None:
    assert coverage_threshold_for(None) == DEFAULT_COVERAGE_THRESHOLD
    assert coverage_threshold_for(0.9) == 0.9
