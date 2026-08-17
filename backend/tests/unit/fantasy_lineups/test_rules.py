"""Unit tests for lineup modules, lock, substitutions and tactical moves."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from auth.exceptions import ValidationAuthError
from database.enums import FantasyModule, FantasyRole, FantasyTurnStatus, LineupSlotKind
from fantasy_lineups.rules import (
    APPROVED_MODULES,
    MAX_AUTOMATIC_SUBSTITUTIONS,
    MAX_TACTICAL_MOVES,
    MIN_AUTOMATIC_SUBSTITUTIONS,
    LineupPlayerRef,
    assert_bench_order_lock,
    assert_copy_previous_lineup,
    assert_lineup_modification_allowed,
    assert_progressive_lock,
    assert_tactical_move,
    coerce_max_automatic_substitutions,
    copy_previous_lineup,
    evaluate_bench_order_lock,
    evaluate_lineup,
    evaluate_progressive_lock,
    evaluate_tactical_move,
    is_athlete_kickoff_locked,
    is_lineup_modification_allowed,
    is_tactical_window_active,
    module_counts,
    ordered_bench_from_roster,
    parse_module,
    remaining_roster_for_bench,
    remaining_tactical_moves,
    resolve_automatic_substitutions,
    starter_template,
)


def _ids(prefix: str, count: int) -> list[str]:
    return [f"{prefix}-{index}" for index in range(count)]


def _players(ids: list[str], role: FantasyRole) -> list[LineupPlayerRef]:
    return [LineupPlayerRef(athlete_id=item, role=role) for item in ids]


def _valid_433() -> tuple[list[str], list[LineupPlayerRef], list[LineupPlayerRef]]:
    keepers = _ids("p", 3)
    defenders = _ids("d", 11)
    mids = _ids("c", 11)
    forwards = _ids("a", 10)
    roster = [*keepers, *defenders, *mids, *forwards]
    starters = [
        *_players(keepers[:1], FantasyRole.P),
        *_players(defenders[:4], FantasyRole.D),
        *_players(mids[:3], FantasyRole.C),
        *_players(forwards[:3], FantasyRole.A),
    ]
    starter_ids = [player.athlete_id for player in starters]
    bench_ids = remaining_roster_for_bench(roster, starter_ids)
    role_by_prefix = {
        "p": FantasyRole.P,
        "d": FantasyRole.D,
        "c": FantasyRole.C,
        "a": FantasyRole.A,
    }
    bench = [
        LineupPlayerRef(athlete_id=item, role=role_by_prefix[str(item)[0]]) for item in bench_ids
    ]
    return roster, starters, bench


def test_seven_approved_modules_and_pdca_counts() -> None:
    assert len(APPROVED_MODULES) == 7
    expected = {
        FantasyModule.M343: (1, 3, 4, 3),
        FantasyModule.M352: (1, 3, 5, 2),
        FantasyModule.M433: (1, 4, 3, 3),
        FantasyModule.M442: (1, 4, 4, 2),
        FantasyModule.M451: (1, 4, 5, 1),
        FantasyModule.M532: (1, 5, 3, 2),
        FantasyModule.M541: (1, 5, 4, 1),
    }
    for module, (p_count, d_count, c_count, a_count) in expected.items():
        counts = module_counts(module)
        assert counts.goalkeepers == p_count
        assert counts.defenders == d_count
        assert counts.midfielders == c_count
        assert counts.forwards == a_count
        assert len(starter_template(module)) == 11
    assert parse_module("4-2-3-1") is None


def test_valid_433_is_accepted() -> None:
    roster, starters, bench = _valid_433()
    result = evaluate_lineup(
        module="4-3-3",
        starters=starters,
        bench=bench,
        roster_athlete_ids=roster,
    )
    assert result.valid
    assert result.issues == ()
    assert result.starter_counts == {"P": 1, "D": 4, "C": 3, "A": 3}


def test_incompatible_module_rejected_with_motivation() -> None:
    roster, starters, bench = _valid_433()
    result = evaluate_lineup(
        module="3-5-2",
        starters=starters,
        bench=bench,
        roster_athlete_ids=roster,
    )
    assert not result.valid
    assert any(issue.code == "module_role_mismatch" for issue in result.issues)
    assert any("3-5-2" in issue.message for issue in result.issues)


def test_unknown_module_and_missing_goalkeeper() -> None:
    result = evaluate_lineup(
        module="4-2-3-1",
        starters=_players(_ids("d", 11), FantasyRole.D),
        bench=[],
        roster_athlete_ids=_ids("d", 11),
    )
    assert not result.valid
    codes = {issue.code for issue in result.issues}
    assert "invalid_module" in codes
    assert "goalkeeper_count_invalid" in codes


def test_duplicate_and_non_roster_players() -> None:
    roster, starters, bench = _valid_433()
    starters[1] = LineupPlayerRef(athlete_id=starters[0].athlete_id, role=FantasyRole.D)
    result = evaluate_lineup(
        module="4-3-3",
        starters=starters,
        bench=bench,
        roster_athlete_ids=roster,
    )
    assert any(issue.code == "duplicate_athlete" for issue in result.issues)

    bench[0] = LineupPlayerRef(athlete_id="outsider", role=FantasyRole.A)
    result = evaluate_lineup(
        module="4-3-3",
        starters=_valid_433()[1],
        bench=[bench[0], *bench[1:]],
        roster_athlete_ids=roster,
    )
    assert any(issue.code == "athlete_not_in_roster" for issue in result.issues)


def test_lineup_turn_gate_allows_open_and_locked() -> None:
    assert is_lineup_modification_allowed(stored=FantasyTurnStatus.OPEN)
    assert is_lineup_modification_allowed(stored=FantasyTurnStatus.LOCKED)
    assert not is_lineup_modification_allowed(stored=FantasyTurnStatus.SCHEDULED)
    assert not is_lineup_modification_allowed(stored=FantasyTurnStatus.SKIPPED)


def test_athlete_lock_simultaneous_kickoffs_and_future_players() -> None:
    kickoff = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    now_before = datetime(2026, 8, 15, 15, 59, 59, tzinfo=UTC)
    now_at = kickoff
    assert not is_athlete_kickoff_locked(now=now_before, kickoff_at=kickoff, status_short="NS")
    assert is_athlete_kickoff_locked(now=now_at, kickoff_at=kickoff, status_short="NS")
    # Simultaneous kickoffs share the same instant.
    other = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    assert is_athlete_kickoff_locked(now=now_at, kickoff_at=other, status_short="NS")
    future = datetime(2026, 8, 15, 18, 30, tzinfo=UTC)
    assert not is_athlete_kickoff_locked(now=now_at, kickoff_at=future, status_short="NS")


def test_athlete_lock_timezone_and_status() -> None:
    rome = ZoneInfo("Europe/Rome")
    kickoff_rome = datetime(2026, 8, 15, 18, 0, tzinfo=rome)
    assert kickoff_rome.astimezone(UTC) == datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    assert not is_athlete_kickoff_locked(
        now=datetime(2026, 8, 15, 15, 59, tzinfo=UTC),
        kickoff_at=kickoff_rome,
        status_short="NS",
    )
    assert is_athlete_kickoff_locked(
        now=datetime(2026, 8, 15, 16, 0, tzinfo=UTC),
        kickoff_at=kickoff_rome,
        status_short="NS",
    )
    assert is_athlete_kickoff_locked(
        now=datetime(2026, 8, 15, 15, 0, tzinfo=UTC),
        kickoff_at=datetime(2026, 8, 15, 18, 0, tzinfo=UTC),
        status_short="1H",
    )
    assert not is_athlete_kickoff_locked(
        now=datetime(2026, 8, 15, 16, 0, tzinfo=UTC),
        kickoff_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        status_short="PST",
    )
    assert not is_athlete_kickoff_locked(
        now=datetime(2026, 8, 15, 16, 0, tzinfo=UTC),
        kickoff_at=None,
    )


def test_athlete_lock_latched_survives_postponement_after_kickoff() -> None:
    now = datetime(2026, 8, 15, 16, 5, tzinfo=UTC)
    postponed = datetime(2026, 8, 16, 16, 0, tzinfo=UTC)
    assert not is_athlete_kickoff_locked(
        now=now,
        kickoff_at=postponed,
        status_short="PST",
        lock_latched=False,
    )
    assert is_athlete_kickoff_locked(
        now=now,
        kickoff_at=postponed,
        status_short="PST",
        lock_latched=True,
    )
    ny = ZoneInfo("America/New_York")
    simultaneous = datetime(2026, 8, 15, 12, 0, tzinfo=ny)
    assert simultaneous.astimezone(UTC) == datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    assert is_athlete_kickoff_locked(
        now=datetime(2026, 8, 15, 16, 0, tzinfo=UTC),
        kickoff_at=simultaneous,
        status_short="NS",
    )


def test_progressive_lock_keeps_future_players_editable() -> None:
    previous = {"locked-a": "starter", "future-b": "bench"}
    proposed_ok = {"locked-a": "starter", "future-b": "starter"}
    issues = evaluate_progressive_lock(
        previous_slots=previous,
        proposed_slots=proposed_ok,
        locked_athlete_ids=["locked-a"],
    )
    assert issues == ()

    proposed_bad = {"locked-a": "bench", "future-b": "starter"}
    issues = evaluate_progressive_lock(
        previous_slots=previous,
        proposed_slots=proposed_bad,
        locked_athlete_ids=["locked-a"],
    )
    assert any(issue.code == "athlete_kickoff_locked" for issue in issues)

    first_save_locked_starter = evaluate_progressive_lock(
        previous_slots={},
        proposed_slots={"locked-a": "starter", "future-b": "bench"},
        locked_athlete_ids=["locked-a"],
    )
    assert any(issue.code == "athlete_kickoff_locked" for issue in first_save_locked_starter)

    first_save_locked_bench = evaluate_progressive_lock(
        previous_slots={},
        proposed_slots={"locked-a": "bench", "future-b": "starter"},
        locked_athlete_ids=["locked-a"],
    )
    assert first_save_locked_bench == ()


def test_assert_lineup_modification_messages() -> None:
    with pytest.raises(ValidationAuthError, match="non è ancora aperto") as scheduled:
        assert_lineup_modification_allowed(stored=FantasyTurnStatus.SCHEDULED)
    assert scheduled.value.code == "turn_not_open"

    with pytest.raises(ValidationAuthError, match="partita è già iniziata") as locked:
        assert_progressive_lock(
            previous_slots={"a": LineupSlotKind.STARTER.value},
            proposed_slots={"a": LineupSlotKind.BENCH.value},
            locked_athlete_ids=["a"],
        )
    assert locked.value.code == "athlete_kickoff_locked"


def test_ordered_bench_preserves_previous_order() -> None:
    assert ordered_bench_from_roster(["p1", "d1", "d2", "c1"], ["p1", "d1"], ["c1", "d2"]) == [
        "c1",
        "d2",
    ]
    assert ordered_bench_from_roster(["p1", "d1", "d2", "c1", "a1"], ["p1", "d1"], ["c1"]) == [
        "c1",
        "d2",
        "a1",
    ]


def test_bench_order_lock_rejects_crossing_locked_player() -> None:
    previous = ["u1", "locked-b", "u2"]
    crossed = evaluate_bench_order_lock(
        previous_bench=previous,
        proposed_bench=["u1", "u2", "locked-b"],
        locked_athlete_ids=["locked-b"],
    )
    assert any(issue.code == "bench_order_locked" for issue in crossed)

    inserted = evaluate_bench_order_lock(
        previous_bench=previous,
        proposed_bench=["u1", "new-d", "locked-b", "u2"],
        locked_athlete_ids=["locked-b"],
    )
    assert any(issue.code == "bench_order_locked" for issue in inserted)

    ok_swap = evaluate_bench_order_lock(
        previous_bench=["u1", "u2", "locked-b"],
        proposed_bench=["u2", "u1", "locked-b"],
        locked_athlete_ids=["locked-b"],
    )
    assert ok_swap == ()

    now = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    rome_kickoff = datetime(2026, 8, 15, 18, 0, tzinfo=ZoneInfo("Europe/Rome"))
    utc_kickoff = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    simultaneous_locked = [
        athlete_id
        for athlete_id, kickoff in (("b-rome", rome_kickoff), ("b-utc", utc_kickoff))
        if is_athlete_kickoff_locked(now=now, kickoff_at=kickoff, status_short="NS")
    ]
    assert simultaneous_locked == ["b-rome", "b-utc"]
    swapped = evaluate_bench_order_lock(
        previous_bench=["b-rome", "b-utc", "future"],
        proposed_bench=["b-utc", "b-rome", "future"],
        locked_athlete_ids=simultaneous_locked,
    )
    assert any(issue.code == "bench_order_locked" for issue in swapped)

    with pytest.raises(ValidationAuthError) as locked:
        assert_bench_order_lock(
            previous_bench=previous,
            proposed_bench=["locked-b", "u1", "u2"],
            locked_athlete_ids=["locked-b"],
        )
    assert locked.value.code == "bench_order_locked"


def test_automatic_substitutions_respect_role_module_order_and_cap() -> None:
    roster, starters, bench = _valid_433()
    first_defender = next(player.athlete_id for player in starters if player.role == FantasyRole.D)
    later_defender = [player.athlete_id for player in bench if player.role == FantasyRole.D][1]
    bench_keeper = next(player.athlete_id for player in bench if player.role == FantasyRole.P)
    played = set(roster)
    played.discard(first_defender)
    reordered_bench = [
        *[player for player in bench if player.athlete_id == later_defender],
        *[player for player in bench if player.athlete_id != later_defender],
    ]
    resolved = resolve_automatic_substitutions(
        module="4-3-3",
        starters=starters,
        bench=reordered_bench,
        played_athlete_ids=list(played),
    )
    assert resolved.module_valid
    assert len(resolved.substitutions) == 1
    assert resolved.substitutions[0].role == FantasyRole.D
    assert resolved.substitutions[0].out_athlete_id == first_defender
    assert resolved.substitutions[0].in_athlete_id == later_defender

    gk_tried = resolve_automatic_substitutions(
        module="4-3-3",
        starters=starters,
        bench=bench,
        played_athlete_ids=[item for item in roster if item != first_defender] + [bench_keeper],
    )
    assert all(item.in_athlete_id != bench_keeper for item in gk_tried.substitutions)

    six_played = set(roster)
    for starter in starters[:6]:
        six_played.discard(starter.athlete_id)
    capped = resolve_automatic_substitutions(
        module="4-3-3",
        starters=starters,
        bench=bench,
        played_athlete_ids=list(six_played),
    )
    assert len(capped.substitutions) == MAX_AUTOMATIC_SUBSTITUTIONS
    assert capped.substitutions[0].order == 1
    assert capped.module_valid


def test_coerce_max_automatic_substitutions_range() -> None:
    assert coerce_max_automatic_substitutions(MIN_AUTOMATIC_SUBSTITUTIONS) == 0
    assert coerce_max_automatic_substitutions(MAX_AUTOMATIC_SUBSTITUTIONS) == 5
    with pytest.raises(ValueError):
        coerce_max_automatic_substitutions(-1)
    with pytest.raises(ValueError):
        coerce_max_automatic_substitutions(6)
    with pytest.raises(ValueError):
        coerce_max_automatic_substitutions(True)  # bool is not an int here


def test_automatic_substitutions_explain_skipped_bench_candidates() -> None:
    """FR-SUB-01: il risultato mostra chi è entrato e perché gli altri sono stati saltati."""
    roster, starters, bench = _valid_433()
    first_defender = next(player.athlete_id for player in starters if player.role == FantasyRole.D)
    bench_defenders = [player.athlete_id for player in bench if player.role == FantasyRole.D]
    replacement_defender, other_defender = bench_defenders[0], bench_defenders[1]
    played = set(roster) - {first_defender, other_defender}

    resolved = resolve_automatic_substitutions(
        module="4-3-3",
        starters=starters,
        bench=bench,
        played_athlete_ids=list(played),
    )
    assert len(resolved.substitutions) == 1
    assert resolved.substitutions[0].in_athlete_id == replacement_defender
    assert resolved.substitutions[0].out_athlete_id == first_defender

    reasons = {item.athlete_id: item.reason for item in resolved.skipped}
    # other_defender non ha voto: non può entrare.
    assert reasons[other_defender] == "not_eligible"
    # I panchinari di ruolo diverso non hanno un titolare senza voto compatibile.
    other_role_bench = [item for item in bench if item.role != FantasyRole.D]
    assert all(reasons[item.athlete_id] == "no_compatible_starter" for item in other_role_bench)
    assert len(resolved.skipped) == len(bench) - 1


def test_automatic_substitutions_respect_league_configurable_limit() -> None:
    roster, starters, bench = _valid_433()
    six_played = set(roster)
    for starter in starters[:6]:
        six_played.discard(starter.athlete_id)

    zero_limit = resolve_automatic_substitutions(
        module="4-3-3",
        starters=starters,
        bench=bench,
        played_athlete_ids=list(six_played),
        max_substitutions=0,
    )
    assert zero_limit.substitutions == ()
    assert all(item.reason == "limit_reached" for item in zero_limit.skipped)

    two_limit = resolve_automatic_substitutions(
        module="4-3-3",
        starters=starters,
        bench=bench,
        played_athlete_ids=list(six_played),
        max_substitutions=2,
    )
    assert len(two_limit.substitutions) == 2


def test_tactical_moves_cap_and_window() -> None:
    assert MAX_TACTICAL_MOVES == 3
    assert remaining_tactical_moves(used=0) == 3
    assert remaining_tactical_moves(used=3) == 0
    assert is_tactical_window_active(any_athlete_locked=False) is False
    assert is_tactical_window_active(any_athlete_locked=True) is True

    initial = evaluate_tactical_move(
        has_saved_lineup=False,
        any_athlete_locked=True,
        moves_used=0,
        proposed_module="4-3-3",
        proposed_starter_ids=["p1", "d1"],
        proposed_bench_ids=["p2"],
    )
    assert initial.would_consume is False
    assert initial.issues == ()

    before_kickoff = evaluate_tactical_move(
        has_saved_lineup=True,
        any_athlete_locked=False,
        moves_used=0,
        proposed_module="4-3-3",
        proposed_starter_ids=["p1", "d2"],
        proposed_bench_ids=["d1"],
        previous_module="4-3-3",
        previous_starter_ids=["p1", "d1"],
        previous_bench_ids=["d2"],
    )
    assert before_kickoff.would_consume is False

    unchanged = evaluate_tactical_move(
        has_saved_lineup=True,
        any_athlete_locked=True,
        moves_used=2,
        proposed_module="4-3-3",
        proposed_starter_ids=["p1", "d1"],
        proposed_bench_ids=["d2"],
        previous_module="4-3-3",
        previous_starter_ids=["p1", "d1"],
        previous_bench_ids=["d2"],
    )
    assert unchanged.would_consume is False

    consume = evaluate_tactical_move(
        has_saved_lineup=True,
        any_athlete_locked=True,
        moves_used=0,
        proposed_module="4-3-3",
        proposed_starter_ids=["p1", "d2"],
        proposed_bench_ids=["d1"],
        previous_module="4-3-3",
        previous_starter_ids=["p1", "d1"],
        previous_bench_ids=["d2"],
    )
    assert consume.would_consume is True
    assert consume.remaining_after == 2
    assert consume.issues == ()

    fourth = evaluate_tactical_move(
        has_saved_lineup=True,
        any_athlete_locked=True,
        moves_used=3,
        proposed_module="4-4-2",
        proposed_starter_ids=["p1", "d2"],
        proposed_bench_ids=["d1"],
        previous_module="4-3-3",
        previous_starter_ids=["p1", "d1"],
        previous_bench_ids=["d2"],
    )
    assert fourth.would_consume is True
    assert any(issue.code == "tactical_moves_exhausted" for issue in fourth.issues)

    with pytest.raises(ValidationAuthError) as exhausted:
        assert_tactical_move(
            has_saved_lineup=True,
            any_athlete_locked=True,
            moves_used=3,
            proposed_module="4-3-3",
            proposed_starter_ids=["p1", "d2"],
            proposed_bench_ids=["d1"],
            previous_module="4-3-3",
            previous_starter_ids=["p1", "d1"],
            previous_bench_ids=["d2"],
        )
    assert exhausted.value.code == "tactical_moves_exhausted"


def test_tactical_move_after_simultaneous_kickoffs_in_timezones() -> None:
    now = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    rome_kickoff = datetime(2026, 8, 15, 18, 0, tzinfo=ZoneInfo("Europe/Rome"))
    utc_kickoff = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    locked = [
        athlete_id
        for athlete_id, kickoff in (("locked-rome", rome_kickoff), ("locked-utc", utc_kickoff))
        if is_athlete_kickoff_locked(now=now, kickoff_at=kickoff, status_short="NS")
    ]
    assert locked == ["locked-rome", "locked-utc"]
    lock_issues = evaluate_progressive_lock(
        previous_slots={"locked-rome": "starter", "locked-utc": "starter", "future": "bench"},
        proposed_slots={"locked-rome": "bench", "locked-utc": "starter", "future": "starter"},
        locked_athlete_ids=locked,
    )
    assert any(issue.code == "athlete_kickoff_locked" for issue in lock_issues)

    allowed = evaluate_tactical_move(
        has_saved_lineup=True,
        any_athlete_locked=True,
        moves_used=2,
        proposed_module="4-3-3",
        proposed_starter_ids=["locked-rome", "locked-utc", "future-b"],
        proposed_bench_ids=["future-a"],
        previous_module="4-3-3",
        previous_starter_ids=["locked-rome", "locked-utc", "future-a"],
        previous_bench_ids=["future-b"],
    )
    assert allowed.would_consume is True
    assert allowed.remaining_after == 0
    assert allowed.issues == ()


def test_draft_evaluation_allows_incomplete_lineup() -> None:
    result = evaluate_lineup(
        module="4-3-3",
        starters=[
            LineupPlayerRef(athlete_id="p-1", role=FantasyRole.P),
            LineupPlayerRef(athlete_id="", role=None),
        ],
        bench=[LineupPlayerRef(athlete_id="d-1", role=FantasyRole.D)],
        roster_athlete_ids=["p-1", "d-1", "c-1"],
        strict=False,
    )
    assert result.valid
    assert result.issues == ()

    duplicate = evaluate_lineup(
        module="4-3-3",
        starters=[
            LineupPlayerRef(athlete_id="p-1", role=FantasyRole.P),
            LineupPlayerRef(athlete_id="p-1", role=FantasyRole.P),
        ],
        bench=[],
        roster_athlete_ids=["p-1"],
        strict=False,
    )
    assert not duplicate.valid
    assert any(issue.code == "duplicate_athlete" for issue in duplicate.issues)


def test_copy_previous_lineup_drops_players_no_longer_in_roster() -> None:
    roster, starters, bench = _valid_433()
    starter_ids = [player.athlete_id for player in starters]
    bench_ids = [player.athlete_id for player in bench]
    dropped_id = starter_ids[4]
    current_roster = [item for item in roster if item != dropped_id]
    role_by_id = {player.athlete_id: player.role for player in [*starters, *bench]}

    copied = copy_previous_lineup(
        previous_module="4-3-3",
        previous_starter_ids=starter_ids,
        previous_bench_ids=bench_ids,
        roster_athlete_ids=current_roster,
        role_by_athlete_id=role_by_id,
    )
    assert copied.blocked is False
    assert copied.can_confirm is False
    assert dropped_id in copied.dropped_athlete_ids
    assert any(issue.code == "copied_athlete_not_in_roster" for issue in copied.issues)
    assert copied.starter_ids[4] == ""
    assert dropped_id not in copied.starter_ids
    assert dropped_id not in copied.bench_ids


def test_copy_previous_lineup_unavailable_on_simultaneous_timezone_kickoffs() -> None:
    now = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    rome = ZoneInfo("Europe/Rome")
    locked = [
        athlete_id
        for athlete_id, kickoff in (
            ("locked-rome", datetime(2026, 8, 15, 18, 0, tzinfo=rome)),
            ("locked-utc", datetime(2026, 8, 15, 16, 0, tzinfo=UTC)),
        )
        if is_athlete_kickoff_locked(now=now, kickoff_at=kickoff, status_short="NS")
    ]
    assert locked == ["locked-rome", "locked-utc"]

    copied = copy_previous_lineup(
        previous_module="4-3-3",
        previous_starter_ids=[
            "locked-rome",
            "locked-utc",
            "p1",
            "d1",
            "d2",
            "d3",
            "c1",
            "c2",
            "a1",
            "a2",
            "a3",
        ],
        previous_bench_ids=["bench-1"],
        roster_athlete_ids=[
            "locked-rome",
            "locked-utc",
            "p1",
            "d1",
            "d2",
            "d3",
            "c1",
            "c2",
            "a1",
            "a2",
            "a3",
            "bench-1",
        ],
        locked_athlete_ids=locked,
    )
    assert copied.starter_ids[0] == ""
    assert copied.starter_ids[1] == ""
    assert "locked-rome" in copied.unavailable_athlete_ids
    assert "locked-utc" in copied.unavailable_athlete_ids
    assert "locked-rome" in copied.bench_ids
    assert any(issue.code == "copied_athlete_unavailable" for issue in copied.issues)
    assert copied.blocked is False

    blocked = copy_previous_lineup(
        previous_module="4-3-3",
        previous_starter_ids=[
            "future",
            "p1",
            "d1",
            "d2",
            "d3",
            "c1",
            "c2",
            "a1",
            "a2",
            "a3",
            "bench-1",
        ],
        previous_bench_ids=["locked-rome"],
        roster_athlete_ids=[
            "future",
            "locked-rome",
            "p1",
            "d1",
            "d2",
            "d3",
            "c1",
            "c2",
            "a1",
            "a2",
            "a3",
            "bench-1",
        ],
        locked_athlete_ids=locked,
        current_confirmed_slots={
            "locked-rome": LineupSlotKind.STARTER.value,
            "p1": LineupSlotKind.STARTER.value,
            "future": LineupSlotKind.BENCH.value,
        },
        current_confirmed_bench=["future"],
    )
    assert blocked.blocked is True
    assert any(issue.code == "athlete_kickoff_locked" for issue in blocked.issues)
    with pytest.raises(ValidationAuthError, match="già iniziata") as error:
        assert_copy_previous_lineup(blocked)
    assert error.value.code == "athlete_kickoff_locked"
