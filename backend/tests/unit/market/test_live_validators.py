"""Unit tests for the EP08-09 follow-up nomination-mode helpers.

Covers the pure functions backing the three new live-auction nomination
modes (turn_based, alphabetical_by_role, random) — no DB session required.
"""

from __future__ import annotations

import random

from market.live_validators import (
    compute_turn_team_index,
    shuffle_athlete_ids,
    sort_athletes_alphabetical_by_role,
)


def test_sort_athletes_alphabetical_by_role_orders_p_d_c_a() -> None:
    athletes = [
        ("id-forward", "A", "Zanetti"),
        ("id-keeper", "P", "Buffon"),
        ("id-midfielder", "C", "Pirlo"),
        ("id-defender", "D", "Maldini"),
    ]
    assert sort_athletes_alphabetical_by_role(athletes) == [
        "id-keeper",
        "id-defender",
        "id-midfielder",
        "id-forward",
    ]


def test_sort_athletes_alphabetical_by_role_orders_by_name_within_role() -> None:
    athletes = [
        ("id-b", "D", "Bastoni"),
        ("id-a", "D", "Acerbi"),
        ("id-c", "D", "Chiellini"),
    ]
    assert sort_athletes_alphabetical_by_role(athletes) == ["id-a", "id-b", "id-c"]


def test_sort_athletes_alphabetical_by_role_is_case_insensitive() -> None:
    athletes = [("id-lower", "P", "buffon"), ("id-upper", "P", "Alisson")]
    assert sort_athletes_alphabetical_by_role(athletes) == ["id-upper", "id-lower"]


def test_sort_athletes_alphabetical_by_role_puts_unknown_role_last() -> None:
    athletes = [("id-unknown", "?", "Aaron"), ("id-forward", "A", "Zanetti")]
    assert sort_athletes_alphabetical_by_role(athletes) == ["id-forward", "id-unknown"]


def test_sort_athletes_alphabetical_by_role_empty_input() -> None:
    assert sort_athletes_alphabetical_by_role([]) == []


def test_shuffle_athlete_ids_is_deterministic_with_seeded_rng() -> None:
    ids = [f"id-{i}" for i in range(20)]
    shuffled_a = shuffle_athlete_ids(ids, rng=random.Random(42))
    shuffled_b = shuffle_athlete_ids(ids, rng=random.Random(42))
    assert shuffled_a == shuffled_b


def test_shuffle_athlete_ids_preserves_the_full_set() -> None:
    ids = [f"id-{i}" for i in range(20)]
    shuffled = shuffle_athlete_ids(ids, rng=random.Random(7))
    assert sorted(shuffled) == sorted(ids)


def test_shuffle_athlete_ids_does_not_mutate_input() -> None:
    ids = ["id-1", "id-2", "id-3"]
    original = list(ids)
    shuffle_athlete_ids(ids, rng=random.Random(1))
    assert ids == original


def test_compute_turn_team_index_cycles_through_teams() -> None:
    # 3 teams: position 0, 1, 2, 0, 1, 2... regardless of how many lots resolved.
    assert compute_turn_team_index(nominated_count=0, team_count=3) == 0
    assert compute_turn_team_index(nominated_count=1, team_count=3) == 1
    assert compute_turn_team_index(nominated_count=2, team_count=3) == 2
    assert compute_turn_team_index(nominated_count=3, team_count=3) == 0
    assert compute_turn_team_index(nominated_count=4, team_count=3) == 1


def test_compute_turn_team_index_single_team_always_zero() -> None:
    assert compute_turn_team_index(nominated_count=0, team_count=1) == 0
    assert compute_turn_team_index(nominated_count=9, team_count=1) == 0


def test_compute_turn_team_index_returns_none_without_teams() -> None:
    assert compute_turn_team_index(nominated_count=0, team_count=0) is None

