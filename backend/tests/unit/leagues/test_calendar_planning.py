"""Calendario H2H adattivo sulle finestre europee (EP13-P03 / FR-LEG-04)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from database.enums import FantasyTurnKind
from fantasy_turns.rules import EligibleFixtureRef
from leagues.calendar_planning import (
    CALENDAR_ALGORITHM_VERSION,
    UNUSED_WINDOW_REASON,
    WindowCandidate,
    assert_plan_invariants,
    balance_home_away,
    build_window_candidates,
    cycle_length_for,
    generate_cycles,
    plan_calendar,
    window_bounds_for_kickoff,
    windows_fingerprint,
)

MIN_FIXTURES = 25


def members(count: int) -> list[UUID]:
    return [UUID(int=index + 1) for index in range(count)]


def window(
    index: int,
    *,
    eligible: bool = True,
    kind: FantasyTurnKind | None = None,
) -> WindowCandidate:
    """Finestra sintetica ordinata: una a settimana a partire dal 2026-08-07."""
    start = datetime(2026, 8, 7, tzinfo=UTC) + timedelta(days=7 * index)
    return WindowCandidate(
        start_at=start,
        end_at=start + timedelta(days=4),
        kind=kind or FantasyTurnKind.WEEKEND,
        timezone="Europe/Rome",
        fixture_count=MIN_FIXTURES if eligible else 3,
        min_required=MIN_FIXTURES,
        eligible=eligible,
        reason=None if eligible else "Soglia non raggiunta: 3 partite eleggibili su 25 richieste.",
    )


def windows(count: int) -> list[WindowCandidate]:
    return [window(index) for index in range(count)]


# --------------------------------------------------------------------------
# Lunghezza del ciclo
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("participants", "expected"),
    [(4, 3), (5, 5), (6, 5), (7, 7), (8, 7), (9, 9), (10, 9)],
)
def test_cycle_length_follows_parity(participants: int, expected: int) -> None:
    """N-1 giornate con N pari, N con N dispari (una di riposo a testa)."""
    assert cycle_length_for(participants) == expected


def test_cycle_length_requires_at_least_two_participants() -> None:
    with pytest.raises(ValueError):
        cycle_length_for(1)


# --------------------------------------------------------------------------
# Invarianti su 4..10 partecipanti
# --------------------------------------------------------------------------


@pytest.mark.parametrize("participants", [4, 5, 6, 7, 8, 9, 10])
def test_plan_satisfies_invariants_for_every_league_size(participants: int) -> None:
    ids = members(participants)
    plan = plan_calendar(ids, windows(40))
    assert_plan_invariants(plan, ids)
    assert plan.cycle_count >= 1
    assert plan.algorithm_version == CALENDAR_ALGORITHM_VERSION


@pytest.mark.parametrize("participants", [4, 5, 6, 7, 8, 9, 10])
def test_every_pair_meets_exactly_once_per_cycle(participants: int) -> None:
    ids = members(participants)
    plan = plan_calendar(ids, windows(40))

    counts: dict[frozenset[UUID], int] = {}
    for slot in plan.slots:
        if slot.is_bye:
            continue
        assert slot.away_membership_id is not None
        pair = frozenset((slot.home_membership_id, slot.away_membership_id))
        counts[pair] = counts.get(pair, 0) + 1

    expected_pairs = participants * (participants - 1) // 2
    assert len(counts) == expected_pairs
    assert set(counts.values()) == {plan.cycle_count}


@pytest.mark.parametrize("participants", [5, 7, 9])
def test_odd_leagues_give_exactly_one_bye_per_team_per_cycle(participants: int) -> None:
    ids = members(participants)
    plan = plan_calendar(ids, windows(40))

    for cycle in range(1, plan.cycle_count + 1):
        first = (cycle - 1) * plan.cycle_length + 1
        last = cycle * plan.cycle_length
        resting = [
            slot.home_membership_id
            for slot in plan.slots
            if slot.is_bye and first <= slot.round_number <= last
        ]
        assert sorted(resting, key=str) == sorted(ids, key=str)


@pytest.mark.parametrize("participants", [4, 6, 8, 10])
def test_even_leagues_have_no_byes(participants: int) -> None:
    ids = members(participants)
    plan = plan_calendar(ids, windows(40))
    assert plan.bye_count == 0


@pytest.mark.parametrize("participants", [4, 5, 6, 7, 8, 9, 10])
def test_home_away_difference_stays_balanced(participants: int) -> None:
    ids = members(participants)
    plan = plan_calendar(ids, windows(40))

    home: dict[UUID, int] = dict.fromkeys(ids, 0)
    away: dict[UUID, int] = dict.fromkeys(ids, 0)
    for slot in plan.slots:
        if slot.is_bye or slot.away_membership_id is None:
            continue
        home[slot.home_membership_id] += 1
        away[slot.away_membership_id] += 1

    # Con cicli alternati lo squilibrio non deve superare una partita.
    assert all(abs(home[team] - away[team]) <= 1 for team in ids)


def home_away_diffs(plan_slots: object, ids: list[UUID]) -> list[int]:
    home: dict[UUID, int] = dict.fromkeys(ids, 0)
    away: dict[UUID, int] = dict.fromkeys(ids, 0)
    for slot in plan_slots:  # type: ignore[attr-defined]
        if slot.is_bye or slot.away_membership_id is None:
            continue
        home[slot.home_membership_id] += 1
        away[slot.away_membership_id] += 1
    return sorted(home[team] - away[team] for team in ids)


@pytest.mark.parametrize("participants", [5, 7, 9])
def test_odd_leagues_reach_perfect_home_away_balance(participants: int) -> None:
    """Con N dispari ogni squadra gioca N-1 partite (numero pari): scarto 0."""
    ids = members(participants)
    plan = plan_calendar(ids, windows(40))
    assert set(home_away_diffs(plan.slots, ids)) == {0}


@pytest.mark.parametrize("participants", [4, 6, 8, 10])
def test_even_leagues_stay_within_one_match(participants: int) -> None:
    """Con N pari ogni squadra gioca N-1 partite (dispari): ±1 è il minimo."""
    ids = members(participants)
    plan = plan_calendar(ids, windows(40))
    assert max(abs(diff) for diff in home_away_diffs(plan.slots, ids)) <= 1


@pytest.mark.parametrize("participants", [4, 5, 6, 7, 8, 9, 10])
def test_an_even_number_of_cycles_balances_perfectly(participants: int) -> None:
    """Con andata e ritorno completi ogni coppia si inverte: scarto zero."""
    ids = members(participants)
    slots = generate_cycles(ids, cycle_count=2)
    assert set(home_away_diffs(slots, ids)) == {0}


def test_seven_participants_do_not_inherit_the_greedy_local_optimum() -> None:
    """Regressione: il rebalance greedy di EP03-06 lasciava uno scarto di ±2.

    Con un numero dispari di cicli l'alternanza non lo annulla, quindi il
    riequilibrio del ciclo base deve essere ottimale.
    """
    ids = members(7)
    slots = generate_cycles(ids, cycle_count=5)
    assert set(home_away_diffs(slots, ids)) == {0}


@pytest.mark.parametrize("participants", [4, 5, 8, 10])
def test_generation_is_deterministic(participants: int) -> None:
    ids = members(participants)
    first = plan_calendar(ids, windows(40))
    second = plan_calendar(list(reversed(ids)), windows(40))
    assert first.slots == second.slots
    assert first.rounds == second.rounds


def test_second_cycle_mirrors_home_and_away() -> None:
    ids = members(4)
    plan = plan_calendar(ids, windows(6))
    assert plan.cycle_count == 2

    first_cycle = {
        (slot.round_number, slot.slot_index): (slot.home_membership_id, slot.away_membership_id)
        for slot in plan.slots
        if slot.round_number <= plan.cycle_length
    }
    for slot in plan.slots:
        if slot.round_number <= plan.cycle_length:
            continue
        key = (slot.round_number - plan.cycle_length, slot.slot_index)
        home, away = first_cycle[key]
        assert (slot.home_membership_id, slot.away_membership_id) == (away, home)


# --------------------------------------------------------------------------
# Selezione delle finestre
# --------------------------------------------------------------------------


def test_only_eligible_windows_host_a_matchday() -> None:
    ids = members(4)  # ciclo da 3 giornate
    mixed = [window(0), window(1, eligible=False), window(2), window(3), window(4)]
    plan = plan_calendar(ids, mixed)

    assert plan.cycle_count == 1
    used_starts = [round_.window_start_at for round_ in plan.rounds]
    assert window(1).start_at not in used_starts
    assert len(used_starts) == 3


def test_discarded_windows_carry_a_reason() -> None:
    ids = members(4)
    mixed = [window(0), window(1, eligible=False), window(2), window(3), window(4)]
    plan = plan_calendar(ids, mixed)

    by_start = {item.start_at: item for item in plan.windows_discarded}
    below_threshold = by_start[window(1).start_at]
    assert below_threshold.eligible is False
    assert "Soglia non raggiunta" in (below_threshold.reason or "")

    leftover = by_start[window(4).start_at]
    assert leftover.eligible is True
    assert leftover.reason == UNUSED_WINDOW_REASON


def test_no_partial_cycles_are_created() -> None:
    ids = members(4)  # ciclo da 3 giornate
    plan = plan_calendar(ids, windows(5))
    # 5 finestre eleggibili: un solo ciclo completo, 2 finestre avanzano.
    assert plan.cycle_count == 1
    assert plan.round_count == 3
    assert len(plan.windows_used) == 3
    assert sum(1 for item in plan.windows_discarded if item.eligible) == 2


def test_plan_is_not_generatable_without_a_full_cycle() -> None:
    ids = members(6)  # ciclo da 5 giornate
    plan = plan_calendar(ids, windows(4))
    assert plan.cycle_count == 0
    assert plan.is_generatable is False
    assert plan.slots == ()
    assert plan.rounds == ()
    assert_plan_invariants(plan, ids)


@pytest.mark.parametrize("participants", [0, 1])
def test_preview_survives_a_league_without_enough_participants(participants: int) -> None:
    """La preview è raggiungibile in `configuring`, con il solo owner iscritto."""
    ids = members(participants)
    plan = plan_calendar(ids, windows(10))

    assert plan.cycle_length == 0
    assert plan.cycle_count == 0
    assert plan.is_generatable is False
    assert plan.slots == ()
    assert plan.rounds == ()
    # Le finestre restano visibili nella diagnostica.
    assert len(plan.windows_discarded) == 10
    assert plan.eligible_window_count == 10
    assert_plan_invariants(plan, ids)


def test_max_cycles_caps_the_plan() -> None:
    ids = members(4)
    plan = plan_calendar(ids, windows(40), max_cycles=2)
    assert plan.cycle_count == 2
    assert plan.round_count == 6


def test_rounds_map_to_windows_in_chronological_order() -> None:
    ids = members(4)
    plan = plan_calendar(ids, windows(6))
    starts = [round_.window_start_at for round_ in plan.rounds]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)


def test_fingerprint_changes_when_eligible_windows_change() -> None:
    base = windows(6)
    moved = [*windows(5), window(9)]
    assert windows_fingerprint(base) != windows_fingerprint(moved)


def test_fingerprint_ignores_non_eligible_windows() -> None:
    base = windows(4)
    with_noise = [*base, window(7, eligible=False)]
    assert windows_fingerprint(base) == windows_fingerprint(with_noise)


# --------------------------------------------------------------------------
# Costruzione delle finestre dalle fixture
# --------------------------------------------------------------------------


def fixture_at(moment: datetime, *, status: str = "NS") -> EligibleFixtureRef:
    return EligibleFixtureRef(fixture_id=object(), kickoff_at=moment, status_short=status)


def test_weekend_and_midweek_kickoffs_land_in_different_windows() -> None:
    # 2026-08-07 è un venerdì, 2026-08-11 un martedì (Europe/Rome).
    friday = datetime(2026, 8, 7, 18, 0, tzinfo=UTC)
    tuesday = datetime(2026, 8, 11, 18, 0, tzinfo=UTC)

    friday_window = window_bounds_for_kickoff(friday)
    tuesday_window = window_bounds_for_kickoff(tuesday)

    assert friday_window[2] == FantasyTurnKind.WEEKEND
    assert tuesday_window[2] == FantasyTurnKind.MIDWEEK
    assert friday_window[:2] != tuesday_window[:2]


def test_monday_kickoff_belongs_to_the_previous_weekend_window() -> None:
    friday = datetime(2026, 8, 7, 18, 0, tzinfo=UTC)
    monday = datetime(2026, 8, 10, 18, 0, tzinfo=UTC)
    assert window_bounds_for_kickoff(monday)[:2] == window_bounds_for_kickoff(friday)[:2]


def test_window_is_eligible_only_above_the_documented_threshold() -> None:
    friday = datetime(2026, 8, 7, 18, 0, tzinfo=UTC)
    enough = [fixture_at(friday + timedelta(minutes=index)) for index in range(MIN_FIXTURES)]
    candidates = build_window_candidates(enough, min_fixtures=MIN_FIXTURES)
    assert len(candidates) == 1
    assert candidates[0].eligible is True
    assert candidates[0].fixture_count == MIN_FIXTURES

    too_few = enough[:-1]
    candidates = build_window_candidates(too_few, min_fixtures=MIN_FIXTURES)
    assert candidates[0].eligible is False
    assert "Soglia non raggiunta" in (candidates[0].reason or "")


def test_cancelled_fixtures_do_not_make_a_window_eligible() -> None:
    friday = datetime(2026, 8, 7, 18, 0, tzinfo=UTC)
    fixtures = [
        fixture_at(friday + timedelta(minutes=index), status="CANC")
        for index in range(MIN_FIXTURES)
    ]
    candidates = build_window_candidates(fixtures, min_fixtures=MIN_FIXTURES)
    assert candidates == ()


def test_candidates_are_sorted_chronologically() -> None:
    later = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    earlier = datetime(2026, 8, 7, 18, 0, tzinfo=UTC)
    fixtures = [fixture_at(later), fixture_at(earlier)]
    candidates = build_window_candidates(fixtures, min_fixtures=10)
    assert [item.start_at for item in candidates] == sorted(item.start_at for item in candidates)


def test_generate_cycles_returns_nothing_for_zero_cycles() -> None:
    assert generate_cycles(members(4), cycle_count=0) == ()


def test_balance_home_away_preserves_pairings_rounds_and_byes() -> None:
    """Il riequilibrio può solo invertire casa/trasferta, mai altro."""
    ids = members(7)
    original = generate_cycles(ids, cycle_count=1)
    balanced = balance_home_away(original)

    assert len(balanced) == len(original)
    for before, after in zip(original, balanced, strict=True):
        assert after.round_number == before.round_number
        assert after.slot_index == before.slot_index
        assert after.is_bye == before.is_bye
        if before.is_bye:
            assert after.home_membership_id == before.home_membership_id
            assert after.away_membership_id is None
        else:
            assert {after.home_membership_id, after.away_membership_id} == {
                before.home_membership_id,
                before.away_membership_id,
            }
