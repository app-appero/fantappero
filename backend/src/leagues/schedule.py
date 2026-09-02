"""Deterministic balanced H2H schedule generation (EP03-06 / FR-LEG-04)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

CALENDAR_ALGORITHM_VERSION = "circle_rr_v1"


@dataclass(frozen=True)
class GeneratedSlot:
    round_number: int
    slot_index: int
    is_bye: bool
    home_membership_id: UUID
    away_membership_id: UUID | None


@dataclass(frozen=True)
class GeneratedSchedule:
    algorithm_version: str
    participant_count: int
    round_count: int
    matchup_count: int
    bye_count: int
    slots: tuple[GeneratedSlot, ...]


def generate_single_round_robin(membership_ids: list[UUID]) -> GeneratedSchedule:
    """Build a single round-robin (andata) with balanced home/away and explicit byes."""
    ordered = sorted(membership_ids, key=lambda value: str(value))
    participant_count = len(ordered)
    rotating: list[UUID | None] = list(ordered)
    if participant_count % 2 == 1:
        rotating.append(None)

    size = len(rotating)
    round_count = size - 1
    half = size // 2
    slots: list[GeneratedSlot] = []
    bye_count = 0
    matchup_count = 0
    home_counts: dict[UUID, int] = defaultdict(int)

    for round_index in range(round_count):
        round_number = round_index + 1
        slot_index = 0
        for pair_index in range(half):
            left = rotating[pair_index]
            right = rotating[size - 1 - pair_index]
            if left is None or right is None:
                resting = right if left is None else left
                assert resting is not None
                slots.append(
                    GeneratedSlot(
                        round_number=round_number,
                        slot_index=slot_index,
                        is_bye=True,
                        home_membership_id=resting,
                        away_membership_id=None,
                    )
                )
                bye_count += 1
            else:
                if home_counts[left] <= home_counts[right]:
                    home, away = left, right
                else:
                    home, away = right, left
                home_counts[home] += 1
                slots.append(
                    GeneratedSlot(
                        round_number=round_number,
                        slot_index=slot_index,
                        is_bye=False,
                        home_membership_id=home,
                        away_membership_id=away,
                    )
                )
                matchup_count += 1
            slot_index += 1
        rotating = [rotating[0], rotating[-1], *rotating[1:-1]]

    rebalanced = _rebalance_home_away(slots)
    return GeneratedSchedule(
        algorithm_version=CALENDAR_ALGORITHM_VERSION,
        participant_count=participant_count,
        round_count=round_count,
        matchup_count=matchup_count,
        bye_count=bye_count,
        slots=tuple(rebalanced),
    )


def _rebalance_home_away(slots: list[GeneratedSlot]) -> list[GeneratedSlot]:
    """Greedy flips that keep pairings while balancing home/away counts."""
    result = list(slots)
    home_counts: dict[UUID, int] = defaultdict(int)
    away_counts: dict[UUID, int] = defaultdict(int)
    for slot in result:
        if slot.is_bye:
            continue
        home_counts[slot.home_membership_id] += 1
        assert slot.away_membership_id is not None
        away_counts[slot.away_membership_id] += 1

    def imbalance(member_id: UUID) -> int:
        return abs(home_counts[member_id] - away_counts[member_id])

    improved = True
    while improved:
        improved = False
        for index, slot in enumerate(result):
            if slot.is_bye or slot.away_membership_id is None:
                continue
            home = slot.home_membership_id
            away = slot.away_membership_id
            before = imbalance(home) + imbalance(away)
            # Simulate flip.
            home_counts[home] -= 1
            away_counts[away] -= 1
            home_counts[away] += 1
            away_counts[home] += 1
            after = imbalance(home) + imbalance(away)
            if after < before:
                result[index] = GeneratedSlot(
                    round_number=slot.round_number,
                    slot_index=slot.slot_index,
                    is_bye=False,
                    home_membership_id=away,
                    away_membership_id=home,
                )
                improved = True
            else:
                home_counts[home] += 1
                away_counts[away] += 1
                home_counts[away] -= 1
                away_counts[home] -= 1
    return result


def participant_fingerprint(membership_ids: list[UUID]) -> str:
    """Stable fingerprint of the participant set used for the calendar."""
    payload = ",".join(sorted(str(value) for value in membership_ids))
    return sha256(payload.encode("utf-8")).hexdigest()


def assert_schedule_invariants(schedule: GeneratedSchedule, membership_ids: list[UUID]) -> None:
    """Raise AssertionError if the schedule violates FR-LEG-04 acceptance rules."""
    ids = set(membership_ids)
    expected_matchups = len(membership_ids) * (len(membership_ids) - 1) // 2
    if schedule.matchup_count != expected_matchups:
        raise AssertionError("unexpected matchup count")
    expected_rounds = (
        len(membership_ids) if len(membership_ids) % 2 else len(membership_ids) - 1
    )
    if schedule.round_count != expected_rounds:
        raise AssertionError("unexpected round count")

    pair_seen: set[frozenset[UUID]] = set()
    by_round: dict[int, list[GeneratedSlot]] = {}
    for slot in schedule.slots:
        by_round.setdefault(slot.round_number, []).append(slot)

    for round_number, round_slots in by_round.items():
        appearing: list[UUID] = []
        for slot in round_slots:
            appearing.append(slot.home_membership_id)
            if slot.is_bye:
                if slot.away_membership_id is not None:
                    raise AssertionError(f"bye has opponent in round {round_number}")
            else:
                if slot.away_membership_id is None:
                    raise AssertionError(f"matchup missing away in round {round_number}")
                appearing.append(slot.away_membership_id)
                pair = frozenset((slot.home_membership_id, slot.away_membership_id))
                if pair in pair_seen:
                    raise AssertionError("duplicate pairing")
                pair_seen.add(pair)
        if len(appearing) != len(set(appearing)):
            raise AssertionError(f"team plays twice in round {round_number}")
        if not set(appearing).issubset(ids):
            raise AssertionError("unknown membership in schedule")
        missing = ids - set(appearing)
        if missing:
            raise AssertionError("missing team in round")

    if len(pair_seen) != expected_matchups:
        raise AssertionError("incomplete pairing coverage")
