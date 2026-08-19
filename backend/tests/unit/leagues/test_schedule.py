"""Unit tests for balanced H2H schedule generation (EP03-06)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from leagues.schedule import (
    assert_schedule_invariants,
    generate_single_round_robin,
    participant_fingerprint,
)


@pytest.mark.parametrize("size", [4, 5, 6, 7, 8, 9, 10])
def test_single_round_robin_is_balanced_for_supported_sizes(size: int) -> None:
    membership_ids = [uuid4() for _ in range(size)]
    schedule = generate_single_round_robin(membership_ids)

    assert_schedule_invariants(schedule, membership_ids)
    assert schedule.participant_count == size
    assert schedule.matchup_count == size * (size - 1) // 2
    assert schedule.round_count == (size if size % 2 else size - 1)
    assert schedule.bye_count == (size if size % 2 else 0)

    home_counts: dict = {member_id: 0 for member_id in membership_ids}
    away_counts: dict = {member_id: 0 for member_id in membership_ids}
    for slot in schedule.slots:
        if slot.is_bye:
            continue
        home_counts[slot.home_membership_id] += 1
        assert slot.away_membership_id is not None
        away_counts[slot.away_membership_id] += 1

    games = size - 1
    for member_id in membership_ids:
        assert home_counts[member_id] + away_counts[member_id] == games
        # Pairings are exact; home/away is balanced within two games.
        assert abs(home_counts[member_id] - away_counts[member_id]) <= 2


def test_generation_is_deterministic_for_same_participant_set() -> None:
    membership_ids = [uuid4() for _ in range(6)]
    first = generate_single_round_robin(membership_ids)
    second = generate_single_round_robin(list(reversed(membership_ids)))
    assert first.slots == second.slots
    assert participant_fingerprint(membership_ids) == participant_fingerprint(
        list(reversed(membership_ids))
    )
