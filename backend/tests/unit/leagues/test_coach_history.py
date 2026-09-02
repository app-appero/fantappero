"""Storico fantallenatore: solo fatti osservabili (EP13-P06)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from leagues.coach_history import (
    ConcludedPlacement,
    build_history,
    placements_page,
    seniority_label,
    summary_line,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def placement(
    *,
    season: int = 2026,
    position: int = 1,
    participants: int = 8,
    played: int = 10,
    points: int = 20,
    fantasy_points: float = 0.0,
) -> ConcludedPlacement:
    return ConcludedPlacement(
        season_year=season,
        position=position,
        participant_count=participants,
        played=played,
        points=points,
        fantasy_points=fantasy_points,
    )


# ---------------------------------------------------------------------------
# Aggregazione
# ---------------------------------------------------------------------------


def test_empty_history_has_no_best_position() -> None:
    history = build_history([])
    assert history.concluded_leagues == 0
    assert history.best_position is None
    assert history.placements == ()
    assert history.has_history is False


def test_fantasy_points_pass_through_untouched() -> None:
    """Fantapunti (magic) e punti classifica (esito) restano campi distinti."""
    history = build_history([placement(points=20, fantasy_points=487.5)])
    assert history.placements[0].points == 20
    assert history.placements[0].fantasy_points == 487.5


def test_best_position_is_the_lowest_number() -> None:
    history = build_history([placement(position=5), placement(position=2), placement(position=9)])
    assert history.best_position == 2
    assert history.concluded_leagues == 3


def test_placements_are_ordered_by_most_recent_season_first() -> None:
    history = build_history(
        [
            placement(season=2024, position=1),
            placement(season=2026, position=4),
            placement(season=2025, position=2),
        ]
    )
    assert [item.season_year for item in history.placements] == [2026, 2025, 2024]


def test_ordering_is_deterministic_within_the_same_season() -> None:
    first = build_history(
        [
            placement(season=2026, position=3, participants=10),
            placement(season=2026, position=1, participants=8),
        ]
    )
    second = build_history(
        [
            placement(season=2026, position=1, participants=8),
            placement(season=2026, position=3, participants=10),
        ]
    )
    assert first.placements == second.placements


def test_placement_keeps_participant_count_for_context() -> None:
    """Un 3º su 4 non vale un 3º su 10: il denominatore va conservato."""
    history = build_history([placement(position=3, participants=4)])
    assert history.placements[0].participant_count == 4


# ---------------------------------------------------------------------------
# Riga sintetica
# ---------------------------------------------------------------------------


def test_summary_is_neutral_when_there_is_no_history() -> None:
    """Un nuovo iscritto non deve sembrare un cattivo fantallenatore."""
    assert summary_line(build_history([])) == "Nessuna lega conclusa"


def test_summary_uses_singular_for_a_single_league() -> None:
    assert summary_line(build_history([placement(position=2)])) == "1 lega conclusa · miglior 2º"


def test_summary_reports_count_and_best_position() -> None:
    history = build_history([placement(position=4), placement(position=2), placement(position=7)])
    assert summary_line(history) == "3 leghe concluse · miglior 2º"


# ---------------------------------------------------------------------------
# Anzianità
# ---------------------------------------------------------------------------


def test_seniority_is_month_and_year_not_an_exact_date() -> None:
    assert seniority_label(datetime(2025, 3, 17, 9, 30, tzinfo=UTC), now=NOW) == "03/2025"


def test_seniority_pads_single_digit_months() -> None:
    assert seniority_label(datetime(2026, 1, 5, tzinfo=UTC), now=NOW) == "01/2026"


def test_seniority_is_absent_without_a_creation_date() -> None:
    assert seniority_label(None, now=NOW) is None


def test_future_creation_date_yields_nothing_instead_of_a_wrong_value() -> None:
    assert seniority_label(NOW + timedelta(days=1), now=NOW) is None


# ---------------------------------------------------------------------------
# Paginazione
# ---------------------------------------------------------------------------


def test_placements_page_returns_the_requested_slice_and_total() -> None:
    items = [placement(season=2026 - index) for index in range(5)]
    page, total = placements_page(items, page=2, page_size=2)
    assert total == 5
    assert page == (items[2], items[3])


def test_page_beyond_the_end_is_empty_but_total_stays_truthful() -> None:
    items = [placement()]
    page, total = placements_page(items, page=9, page_size=10)
    assert page == ()
    assert total == 1


@pytest.mark.parametrize(("page", "size"), [(0, 10), (1, 0), (-1, -1)])
def test_invalid_pagination_returns_nothing_without_crashing(page: int, size: int) -> None:
    items = [placement()]
    result, total = placements_page(items, page=page, page_size=size)
    assert result == ()
    assert total == 1
