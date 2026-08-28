"""Timeline live e freschezza del feed provider (EP13-P04)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fantasy_turns.live_view import (
    FixtureFreshness,
    ProviderFeedState,
    RawTimelineEvent,
    build_timeline,
    fixture_feed_state,
    minute_label,
    turn_feed_state,
)

NOW = datetime(2026, 8, 22, 20, 0, tzinfo=UTC)


def fixture(status: str, *, age_minutes: float | None = 0.0) -> FixtureFreshness:
    updated = None if age_minutes is None else NOW - timedelta(minutes=age_minutes)
    return FixtureFreshness(status_short=status, updated_at=updated)


# ---------------------------------------------------------------------------
# Freschezza per singola partita
# ---------------------------------------------------------------------------


def test_live_fixture_updated_recently_is_fresh() -> None:
    assert fixture_feed_state(fixture("1H", age_minutes=0.5), now=NOW) is ProviderFeedState.FRESH


def test_live_fixture_is_delayed_after_two_minutes() -> None:
    assert fixture_feed_state(fixture("2H", age_minutes=3), now=NOW) is ProviderFeedState.DELAYED


def test_live_fixture_is_stale_after_ten_minutes() -> None:
    assert fixture_feed_state(fixture("2H", age_minutes=15), now=NOW) is ProviderFeedState.STALE


def test_thresholds_are_inclusive_at_the_boundary() -> None:
    assert fixture_feed_state(fixture("1H", age_minutes=2), now=NOW) is ProviderFeedState.DELAYED
    assert fixture_feed_state(fixture("1H", age_minutes=10), now=NOW) is ProviderFeedState.STALE


@pytest.mark.parametrize("status", ["NS", "FT", "AET", "PEN", "PST", "CANC"])
def test_non_live_fixtures_are_never_flagged_as_late(status: str) -> None:
    """Una partita non in corso non deve aggiornarsi: il silenzio è normale."""
    assert fixture_feed_state(fixture(status, age_minutes=600), now=NOW) is ProviderFeedState.FRESH


def test_fixture_without_any_update_is_unavailable() -> None:
    assert (
        fixture_feed_state(fixture("1H", age_minutes=None), now=NOW)
        is ProviderFeedState.UNAVAILABLE
    )


def test_status_comparison_is_case_insensitive() -> None:
    assert fixture_feed_state(fixture("1h", age_minutes=15), now=NOW) is ProviderFeedState.STALE


# ---------------------------------------------------------------------------
# Freschezza aggregata del turno
# ---------------------------------------------------------------------------


def test_turn_without_fixtures_is_unavailable() -> None:
    assert turn_feed_state([], now=NOW) is ProviderFeedState.UNAVAILABLE


def test_turn_is_fresh_when_every_fixture_is_fresh() -> None:
    fixtures = [fixture("1H", age_minutes=0.5), fixture("FT", age_minutes=200)]
    assert turn_feed_state(fixtures, now=NOW) is ProviderFeedState.FRESH


def test_turn_is_stale_when_every_live_fixture_is_stale() -> None:
    fixtures = [fixture("1H", age_minutes=20), fixture("2H", age_minutes=30)]
    assert turn_feed_state(fixtures, now=NOW) is ProviderFeedState.STALE


def test_turn_is_degraded_when_only_some_fixtures_lag() -> None:
    """Parziale: dire `stale` allarmerebbe troppo, dire `fresh` nasconderebbe."""
    fixtures = [fixture("1H", age_minutes=0.5), fixture("2H", age_minutes=30)]
    assert turn_feed_state(fixtures, now=NOW) is ProviderFeedState.DEGRADED


def test_turn_is_degraded_when_one_fixture_has_no_data() -> None:
    fixtures = [fixture("1H", age_minutes=0.5), fixture("1H", age_minutes=None)]
    assert turn_feed_state(fixtures, now=NOW) is ProviderFeedState.DEGRADED


# ---------------------------------------------------------------------------
# Minuti
# ---------------------------------------------------------------------------


def test_minute_label_formats_regular_and_stoppage_time() -> None:
    assert minute_label(45, None) == "45'"
    assert minute_label(45, 2) == "45+2'"
    assert minute_label(90, 0) == "90'"


def test_minute_label_without_minute_is_not_zero() -> None:
    assert minute_label(None, None) == "—"


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


def event(
    identifier: str,
    *,
    minute: int | None,
    extra: int | None = None,
    active: bool = True,
    retracted: datetime | None = None,
    event_type: str = "Goal",
) -> RawTimelineEvent:
    return RawTimelineEvent(
        id=identifier,
        minute_elapsed=minute,
        minute_extra=extra,
        event_type=event_type,
        event_detail="Normal Goal",
        scoring_kind="goal",
        club_name="Roma",
        athlete_name="Rossi",
        related_athlete_name="Bianchi",
        comments=None,
        is_active=active,
        retracted_at=retracted,
    )


def test_timeline_is_ordered_by_minute_then_stoppage_time() -> None:
    timeline = build_timeline(
        [
            event("c", minute=45, extra=2),
            event("a", minute=12),
            event("b", minute=45),
        ]
    )
    assert [item.id for item in timeline] == ["a", "b", "c"]


def test_retracted_events_disappear_from_the_timeline() -> None:
    """Una correzione tardiva non deve lasciare a schermo un gol annullato."""
    timeline = build_timeline(
        [
            event("kept", minute=10),
            event("inactive", minute=20, active=False),
            event("retracted", minute=30, retracted=NOW),
        ]
    )
    assert [item.id for item in timeline] == ["kept"]


def test_events_without_a_minute_go_last_instead_of_pretending_zero() -> None:
    timeline = build_timeline([event("unknown", minute=None), event("known", minute=5)])
    assert [item.id for item in timeline] == ["known", "unknown"]
    assert timeline[1].minute_elapsed is None


def test_ordering_is_deterministic_for_events_in_the_same_minute() -> None:
    first = build_timeline([event("z", minute=30), event("a", minute=30)])
    second = build_timeline([event("a", minute=30), event("z", minute=30)])
    assert [item.id for item in first] == [item.id for item in second] == ["a", "z"]


def test_timeline_preserves_event_detail_and_assist() -> None:
    timeline = build_timeline([event("goal", minute=33)])
    assert timeline[0].event_type == "Goal"
    assert timeline[0].event_detail == "Normal Goal"
    assert timeline[0].related_athlete_name == "Bianchi"


def test_empty_input_produces_an_empty_timeline() -> None:
    assert build_timeline([]) == ()
