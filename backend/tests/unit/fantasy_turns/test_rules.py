"""Unit tests for european turn window/cutoff rules (EP06-01 / EP06-07)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from auth.exceptions import ValidationAuthError
from database.enums import FantasyTurnStatus
from fantasy_turns.rules import (
    EligibleFixtureRef,
    aggregate_turn_status,
    apply_cutoff_recalculation,
    assert_modification_allowed,
    compute_cutoff,
    derive_effective_status,
    ensure_utc,
    evaluate_threshold,
    full_season_turn_specs,
    is_modification_allowed,
    kickoff_counts_for_cutoff,
    midweek_window,
    reconcile_fixture_kickoff_lock,
    select_eligible_from_candidates,
    upcoming_turn_specs,
    weekend_window,
    window_for_kind,
)


def test_weekend_window_friday_to_monday_rome() -> None:
    window = weekend_window(date(2026, 8, 15))  # Saturday
    # Friday 00:00 Europe/Rome (CEST) = Thursday 22:00 UTC
    assert window.start_at == datetime(2026, 8, 13, 22, 0, tzinfo=UTC)
    # Exclusive Tuesday 00:00 Rome = Monday 22:00 UTC
    assert window.end_at == datetime(2026, 8, 17, 22, 0, tzinfo=UTC)


def test_weekend_window_from_monday_uses_previous_friday() -> None:
    window = weekend_window(date(2026, 8, 17))  # Monday
    assert window.start_at.astimezone(ZoneInfo("Europe/Rome")).date() == date(2026, 8, 14)


def test_midweek_window_tuesday_to_thursday() -> None:
    window = midweek_window(date(2026, 8, 12))  # Wednesday
    local_start = window.start_at.astimezone(ZoneInfo("Europe/Rome"))
    assert local_start.date() == date(2026, 8, 11)
    assert local_start.hour == 0


def test_compute_cutoff_simultaneous_kickoffs() -> None:
    a = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)
    b = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)
    c = datetime(2026, 8, 15, 18, 30, tzinfo=UTC)
    assert compute_cutoff([c, a, b]) == a
    assert compute_cutoff([]) is None


def test_evaluate_threshold_skip_reason() -> None:
    ok = evaluate_threshold(25, 25)
    assert ok.ok
    skip = evaluate_threshold(10, 25)
    assert not skip.ok
    assert skip.skip_reason is not None
    assert "10" in skip.skip_reason


def test_derive_effective_status_locks_open_past_cutoff() -> None:
    cutoff = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    assert (
        derive_effective_status(
            FantasyTurnStatus.OPEN,
            now=datetime(2026, 8, 15, 15, 59, tzinfo=UTC),
            cutoff_at=cutoff,
        )
        == FantasyTurnStatus.OPEN
    )
    assert (
        derive_effective_status(
            FantasyTurnStatus.OPEN,
            now=datetime(2026, 8, 15, 16, 0, tzinfo=UTC),
            cutoff_at=cutoff,
        )
        == FantasyTurnStatus.LOCKED
    )


def test_assert_modification_allowed_rejects_after_open_or_cutoff() -> None:
    cutoff = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    assert_modification_allowed(
        stored=FantasyTurnStatus.SCHEDULED,
        now=datetime(2026, 8, 15, 20, 0, tzinfo=UTC),
        cutoff_at=cutoff,
    )
    with pytest.raises(ValidationAuthError) as open_exc:
        assert_modification_allowed(
            stored=FantasyTurnStatus.OPEN,
            now=datetime(2026, 8, 15, 15, 0, tzinfo=UTC),
            cutoff_at=cutoff,
        )
    assert open_exc.value.code == "turn_already_open"

    with pytest.raises(ValidationAuthError) as locked_exc:
        assert_modification_allowed(
            stored=FantasyTurnStatus.OPEN,
            now=datetime(2026, 8, 15, 17, 0, tzinfo=UTC),
            cutoff_at=cutoff,
        )
    assert locked_exc.value.code == "turn_modification_closed"
    assert not is_modification_allowed(
        stored=FantasyTurnStatus.LOCKED,
        now=datetime(2026, 8, 15, 17, 0, tzinfo=UTC),
        cutoff_at=cutoff,
    )


def test_select_eligible_filters_cancelled_assigned_and_out_of_window() -> None:
    window = weekend_window(date(2026, 8, 15))
    in_window = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)
    outside = datetime(2026, 8, 12, 14, 0, tzinfo=UTC)
    assigned = uuid4()
    ok_id = uuid4()
    candidates = [
        EligibleFixtureRef(fixture_id=ok_id, kickoff_at=in_window, status_short="NS"),
        EligibleFixtureRef(fixture_id=uuid4(), kickoff_at=in_window, status_short="CANC"),
        EligibleFixtureRef(fixture_id=uuid4(), kickoff_at=outside, status_short="NS"),
        EligibleFixtureRef(fixture_id=assigned, kickoff_at=in_window, status_short="NS"),
    ]
    selected = select_eligible_from_candidates(
        candidates,
        window,
        already_assigned_ids={assigned},
    )
    assert [row.fixture_id for row in selected] == [ok_id]


def test_upcoming_turn_specs_covers_weekend_and_midweek() -> None:
    from database.enums import FantasyTurnKind

    specs = upcoming_turn_specs(date(2026, 8, 12), horizon_days=10)
    kinds = {kind for kind, _ in specs}
    assert FantasyTurnKind.WEEKEND in kinds
    assert FantasyTurnKind.MIDWEEK in kinds
    starts = [(kind, window_for_kind(kind, anchor).start_at) for kind, anchor in specs]
    assert len(starts) == len(set(starts))


def test_upcoming_turn_specs_skips_fully_ended_windows() -> None:
    from database.enums import FantasyTurnKind

    specs = upcoming_turn_specs(date(2026, 8, 19), horizon_days=7)  # Wednesday after a weekend
    weekend_anchors = [anchor for kind, anchor in specs if kind == FantasyTurnKind.WEEKEND]
    assert date(2026, 8, 14) not in weekend_anchors


def test_full_season_turn_specs_covers_the_whole_range_in_chronological_order() -> None:
    specs = full_season_turn_specs(date(2026, 8, 1), date(2026, 9, 30))
    starts = [window_for_kind(kind, anchor).start_at for kind, anchor in specs]
    assert starts == sorted(starts)
    assert len(starts) == len(set(starts))
    # Covers both the very first and the very last week of the range.
    assert any(anchor <= date(2026, 8, 7) for _, anchor in specs)
    assert any(anchor >= date(2026, 9, 24) for _, anchor in specs)


def test_full_season_turn_specs_does_not_drop_past_windows_regardless_of_today() -> None:
    """Unlike `upcoming_turn_specs`, must not be anchored to "today" at all."""
    specs = full_season_turn_specs(date(2020, 1, 1), date(2020, 2, 1))
    assert len(specs) > 0


def test_aggregate_turn_status_live_wins_over_everything() -> None:
    ko = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)
    assert aggregate_turn_status([("FT", ko), ("1H", ko)]) == "live"


def test_aggregate_turn_status_needs_update_when_a_fixture_has_no_kickoff() -> None:
    ko = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)
    assert aggregate_turn_status([("NS", ko), ("TBD", None)]) == "needs_update"


def test_aggregate_turn_status_completed_only_when_all_terminal() -> None:
    ko = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)
    assert aggregate_turn_status([("FT", ko), ("AET", ko)]) == "completed"
    assert aggregate_turn_status([("FT", ko), ("NS", ko)]) == "scheduled"


def test_aggregate_turn_status_empty_is_needs_update() -> None:
    assert aggregate_turn_status([]) == "needs_update"


def test_apply_cutoff_recalculation_simultaneous_and_timezones() -> None:
    rome = ZoneInfo("Europe/Rome")
    first = datetime(2026, 8, 15, 18, 0, tzinfo=rome)
    simultaneous = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    later = datetime(2026, 8, 15, 20, 0, tzinfo=UTC)
    now_before = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
    now_after = datetime(2026, 8, 15, 16, 5, tzinfo=UTC)
    assert first.astimezone(UTC) == simultaneous
    assert compute_cutoff([later, first, simultaneous]) == simultaneous

    delayed = apply_cutoff_recalculation(
        previous_cutoff=first,
        candidate_cutoff=later,
        now=now_before,
    )
    assert delayed == later

    latched = apply_cutoff_recalculation(
        previous_cutoff=first,
        candidate_cutoff=later,
        now=now_after,
    )
    assert latched == ensure_utc(first)

    earlier = apply_cutoff_recalculation(
        previous_cutoff=later,
        candidate_cutoff=simultaneous,
        now=now_after,
    )
    assert earlier == simultaneous


def test_kickoff_counts_for_cutoff_excludes_cancelled_and_past_postponed() -> None:
    now = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)
    future = datetime(2026, 8, 16, 16, 0, tzinfo=UTC)
    past = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    assert kickoff_counts_for_cutoff(kickoff_at=future, status_short="NS", now=now)
    assert not kickoff_counts_for_cutoff(kickoff_at=past, status_short="CANC", now=now)
    assert not kickoff_counts_for_cutoff(kickoff_at=past, status_short="PST", now=now)
    assert kickoff_counts_for_cutoff(kickoff_at=future, status_short="PST", now=now)


def test_reconcile_fixture_kickoff_lock_latches_after_elapsed_not_before() -> None:
    rome = ZoneInfo("Europe/Rome")
    original = datetime(2026, 8, 15, 18, 0, tzinfo=rome)
    postponed = datetime(2026, 8, 16, 18, 0, tzinfo=rome)
    before = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
    after = datetime(2026, 8, 15, 16, 5, tzinfo=UTC)

    pre = reconcile_fixture_kickoff_lock(
        now=before,
        current_kickoff_at=postponed,
        status_short="PST",
        observed_kickoff_at=original,
        lock_latched_at=None,
    )
    assert pre.lock_latched_at is None
    assert pre.observed_kickoff_at == postponed.astimezone(UTC)

    post = reconcile_fixture_kickoff_lock(
        now=after,
        current_kickoff_at=postponed,
        status_short="PST",
        observed_kickoff_at=original,
        lock_latched_at=None,
    )
    assert post.lock_latched_at == original.astimezone(UTC)
    assert post.just_latched is True

    already = reconcile_fixture_kickoff_lock(
        now=after,
        current_kickoff_at=postponed,
        status_short="PST",
        observed_kickoff_at=postponed,
        lock_latched_at=original,
    )
    assert already.lock_latched_at == original.astimezone(UTC)
    assert already.just_latched is False


def test_reconcile_fixture_kickoff_lock_time_shift_without_pst() -> None:
    rome = ZoneInfo("Europe/Rome")
    original = datetime(2026, 8, 15, 18, 0, tzinfo=rome)
    shifted = datetime(2026, 8, 15, 20, 30, tzinfo=rome)
    after = datetime(2026, 8, 15, 16, 5, tzinfo=UTC)

    shifted_after = reconcile_fixture_kickoff_lock(
        now=after,
        current_kickoff_at=shifted,
        status_short="NS",
        observed_kickoff_at=original,
        lock_latched_at=None,
    )
    assert shifted_after.lock_latched_at == original.astimezone(UTC)
    assert shifted_after.just_latched is True

    delayed = apply_cutoff_recalculation(
        previous_cutoff=original,
        candidate_cutoff=shifted,
        now=after,
    )
    assert delayed == ensure_utc(original)
