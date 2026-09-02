"""Unit tests for standings aggregation and tie-break (EP07-06 / FR-CLS-01)."""

from __future__ import annotations

from uuid import UUID

from leagues.standings import (
    AWAY_WIN,
    DRAW,
    HOME_WIN,
    MatchResult,
    TeamRecord,
    build_standings,
    rank_standings,
)

TEAM_A = UUID("00000000-0000-0000-0000-00000000000a")
TEAM_B = UUID("00000000-0000-0000-0000-00000000000b")
TEAM_C = UUID("00000000-0000-0000-0000-00000000000c")


def test_build_standings_includes_teams_with_zero_matches() -> None:
    records = build_standings([TEAM_A, TEAM_B, TEAM_C], [])
    assert set(records) == {TEAM_A, TEAM_B, TEAM_C}
    assert all(record.played == 0 for record in records.values())


def test_home_win_updates_both_sides() -> None:
    matches = [
        MatchResult(
            home_team_id=TEAM_A,
            away_team_id=TEAM_B,
            home_fantasy_goals=2,
            away_fantasy_goals=1,
            outcome=HOME_WIN,
        )
    ]
    records = build_standings([TEAM_A, TEAM_B], matches)
    assert records[TEAM_A] == TeamRecord(
        fantasy_team_id=TEAM_A,
        played=1,
        won=1,
        drawn=0,
        lost=0,
        fantasy_goals_for=2,
        fantasy_goals_against=1,
    )
    assert records[TEAM_A].points == 3
    assert records[TEAM_B] == TeamRecord(
        fantasy_team_id=TEAM_B,
        played=1,
        won=0,
        drawn=0,
        lost=1,
        fantasy_goals_for=1,
        fantasy_goals_against=2,
    )
    assert records[TEAM_B].points == 0


def test_draw_updates_both_sides_with_draw_points() -> None:
    matches = [
        MatchResult(
            home_team_id=TEAM_A,
            away_team_id=TEAM_B,
            home_fantasy_goals=1,
            away_fantasy_goals=1,
            outcome=DRAW,
        )
    ]
    records = build_standings([TEAM_A, TEAM_B], matches)
    assert records[TEAM_A].points == 1
    assert records[TEAM_B].points == 1
    assert records[TEAM_A].won == 0
    assert records[TEAM_A].lost == 0


def test_away_win() -> None:
    matches = [
        MatchResult(
            home_team_id=TEAM_A,
            away_team_id=TEAM_B,
            home_fantasy_goals=0,
            away_fantasy_goals=3,
            outcome=AWAY_WIN,
        )
    ]
    records = build_standings([TEAM_A, TEAM_B], matches)
    assert records[TEAM_A].lost == 1
    assert records[TEAM_B].won == 1
    assert records[TEAM_B].points == 3


def test_recompute_replaces_instead_of_accumulating() -> None:
    """FR-CLS-01: il ricalcolo sostituisce il contributo, non lo somma due volte."""
    matches = [
        MatchResult(TEAM_A, TEAM_B, 2, 1, HOME_WIN),
        MatchResult(TEAM_A, TEAM_C, 1, 1, DRAW),
    ]
    first = build_standings([TEAM_A, TEAM_B, TEAM_C], matches)
    second = build_standings([TEAM_A, TEAM_B, TEAM_C], matches)
    assert first == second
    assert first[TEAM_A].played == 2
    assert first[TEAM_A].points == 4  # 3 (vittoria) + 1 (pareggio)


def test_rank_standings_orders_by_points_then_goal_difference_then_goals_for() -> None:
    records = {
        TEAM_A: TeamRecord(
            TEAM_A, played=2, won=1, drawn=1, fantasy_goals_for=4, fantasy_goals_against=2
        ),
        TEAM_B: TeamRecord(
            TEAM_B, played=2, won=1, drawn=0, lost=1, fantasy_goals_for=5, fantasy_goals_against=3
        ),
        TEAM_C: TeamRecord(
            TEAM_C, played=2, won=1, drawn=1, fantasy_goals_for=3, fantasy_goals_against=1
        ),
    }
    # A: 4 punti, diff +2; B: 3 punti, diff +2; C: 4 punti, diff +2, ma meno gol fatti di A.
    ranked = rank_standings(records)
    assert [r.fantasy_team_id for r in ranked] == [TEAM_A, TEAM_C, TEAM_B]


def test_rank_standings_final_tiebreak_is_team_name() -> None:
    tied = {
        TEAM_A: TeamRecord(TEAM_A, played=1, won=1, fantasy_goals_for=1, fantasy_goals_against=0),
        TEAM_B: TeamRecord(TEAM_B, played=1, won=1, fantasy_goals_for=1, fantasy_goals_against=0),
    }
    ranked = rank_standings(tied, team_names={TEAM_A: "Zeta FC", TEAM_B: "Alpha FC"})
    assert [r.fantasy_team_id for r in ranked] == [TEAM_B, TEAM_A]


def test_fantasy_points_are_aggregated_for_and_against() -> None:
    """I Fantapunti si sommano come i gol, ma con i decimali (EP13-P02)."""
    matches = [
        MatchResult(
            home_team_id=TEAM_A,
            away_team_id=TEAM_B,
            home_fantasy_goals=2,
            away_fantasy_goals=1,
            outcome=HOME_WIN,
            home_fantasy_points=72.5,
            away_fantasy_points=68.0,
        ),
        MatchResult(
            home_team_id=TEAM_B,
            away_team_id=TEAM_A,
            home_fantasy_goals=1,
            away_fantasy_goals=1,
            outcome=DRAW,
            home_fantasy_points=70.5,
            away_fantasy_points=70.0,
        ),
    ]
    records = build_standings([TEAM_A, TEAM_B], matches)

    assert records[TEAM_A].fantasy_points_for == 142.5
    assert records[TEAM_A].fantasy_points_against == 138.5
    assert records[TEAM_B].fantasy_points_for == 138.5
    assert records[TEAM_B].fantasy_points_against == 142.5


def test_fantasy_points_accumulate_without_float_drift() -> None:
    """Somme ripetute di decimali non devono produrre 217.29999999999998."""
    matches = [
        MatchResult(
            home_team_id=TEAM_A,
            away_team_id=TEAM_B,
            home_fantasy_goals=1,
            away_fantasy_goals=1,
            outcome=DRAW,
            home_fantasy_points=72.1,
            away_fantasy_points=66.2,
        )
        for _ in range(3)
    ]
    records = build_standings([TEAM_A, TEAM_B], matches)

    assert records[TEAM_A].fantasy_points_for == 216.3
    assert records[TEAM_B].fantasy_points_for == 198.6


def test_missing_fantasy_points_count_as_zero_without_breaking_the_record() -> None:
    """Slot storici senza punti persistiti non devono rompere l'aggregato."""
    matches = [
        MatchResult(
            home_team_id=TEAM_A,
            away_team_id=TEAM_B,
            home_fantasy_goals=2,
            away_fantasy_goals=0,
            outcome=HOME_WIN,
        )
    ]
    records = build_standings([TEAM_A, TEAM_B], matches)

    assert records[TEAM_A].played == 1
    assert records[TEAM_A].fantasy_goals_for == 2
    assert records[TEAM_A].fantasy_points_for == 0.0
    assert records[TEAM_A].fantasy_points_against == 0.0


def test_fantasy_points_do_not_change_the_ranking_criteria() -> None:
    """L'ordinamento resta punti/differenza reti/gol fatti: EP13-P02 non lo tocca."""
    records = {
        TEAM_A: TeamRecord(
            TEAM_A,
            played=1,
            won=1,
            fantasy_goals_for=2,
            fantasy_goals_against=1,
            fantasy_points_for=10.0,
        ),
        TEAM_B: TeamRecord(
            TEAM_B,
            played=1,
            won=1,
            fantasy_goals_for=2,
            fantasy_goals_against=1,
            fantasy_points_for=999.0,
        ),
    }
    ranked = rank_standings(records, team_names={TEAM_A: "Alpha FC", TEAM_B: "Zeta FC"})
    # B ha molti piu' Fantapunti ma resta secondo: lo spareggio e' il nome.
    assert [r.fantasy_team_id for r in ranked] == [TEAM_A, TEAM_B]


def test_as_dict_exposes_both_aggregates_distinctly() -> None:
    record = TeamRecord(
        TEAM_A,
        played=1,
        won=1,
        fantasy_goals_for=2,
        fantasy_goals_against=1,
        fantasy_points_for=72.5,
        fantasy_points_against=68.0,
    )
    payload = record.as_dict()

    assert payload["fantasyGoalsFor"] == 2
    assert payload["fantasyPointsFor"] == 72.5
    assert payload["fantasyGoalsAgainst"] == 1
    assert payload["fantasyPointsAgainst"] == 68.0
    assert payload["points"] == 3
