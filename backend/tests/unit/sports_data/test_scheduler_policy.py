"""Unit tests for sports scheduler windows, quota, locks and policy (EP04-06)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sports_data.provider.types import ProviderRateLimit
from sports_data.scheduler.locks import InMemoryJobLock, hold_job_lock
from sports_data.scheduler.policy import (
    beat_schedule_entries,
    effective_interval_seconds,
    policy_for,
)
from sports_data.scheduler.quota import (
    QuotaMode,
    allow_criticality,
    max_fixtures_for_mode,
    resolve_quota_mode,
)
from sports_data.scheduler.windows import PollWindow, classify_fixture_window


def test_classify_pre_live_post_late() -> None:
    now = datetime(2023, 8, 20, 15, 0, tzinfo=UTC)
    kickoff = now + timedelta(hours=2)
    assert (
        classify_fixture_window(status_short="NS", kickoff_at=kickoff, now=now)
        == PollWindow.PRE_MATCH
    )
    assert (
        classify_fixture_window(status_short="1H", kickoff_at=now - timedelta(minutes=20), now=now)
        == PollWindow.LIVE
    )
    assert (
        classify_fixture_window(
            status_short="FT",
            kickoff_at=now - timedelta(hours=2),
            now=now,
        )
        == PollWindow.POST_MATCH
    )
    assert (
        classify_fixture_window(
            status_short="FT",
            kickoff_at=now - timedelta(hours=10),
            now=now,
        )
        == PollWindow.LATE_CORRECTIONS
    )
    assert (
        classify_fixture_window(
            status_short="FT",
            kickoff_at=now - timedelta(days=5),
            now=now,
        )
        is None
    )
    assert classify_fixture_window(status_short="CANC", kickoff_at=kickoff, now=now) is None


def test_overdue_ns_treated_as_live() -> None:
    now = datetime(2023, 8, 20, 15, 0, tzinfo=UTC)
    kickoff = now - timedelta(minutes=5)
    assert (
        classify_fixture_window(status_short="NS", kickoff_at=kickoff, now=now) == PollWindow.LIVE
    )


def test_quota_mode_thresholds() -> None:
    assert resolve_quota_mode(ProviderRateLimit(limit=100, remaining=50)) == QuotaMode.OK
    assert resolve_quota_mode(ProviderRateLimit(limit=100, remaining=20)) == QuotaMode.WARN
    assert resolve_quota_mode(ProviderRateLimit(limit=100, remaining=10)) == QuotaMode.DEGRADE
    assert resolve_quota_mode(ProviderRateLimit(limit=100, remaining=3)) == QuotaMode.CRITICAL_ONLY
    assert resolve_quota_mode(None) == QuotaMode.OK


def test_degraded_interval_and_criticality_drop() -> None:
    live = policy_for(PollWindow.LIVE)
    assert live.fetch_events is True
    assert live.fetch_players is True
    assert live.players_criticality == "critical"
    assert effective_interval_seconds(PollWindow.LIVE, QuotaMode.OK) == live.base_interval_seconds
    degraded = effective_interval_seconds(PollWindow.LIVE, QuotaMode.DEGRADE)
    assert degraded == live.base_interval_seconds * 2.5
    assert allow_criticality("low", QuotaMode.DEGRADE) is False
    assert allow_criticality("critical", QuotaMode.CRITICAL_ONLY) is True
    assert allow_criticality("medium", QuotaMode.CRITICAL_ONLY) is False
    assert max_fixtures_for_mode(40, QuotaMode.DEGRADE) == 20


def test_in_memory_lock_prevents_concurrent() -> None:
    lock = InMemoryJobLock()
    first = lock.try_acquire("live", ttl_seconds=30)
    assert first is not None
    assert lock.try_acquire("live", ttl_seconds=30) is None
    assert lock.release("live", first) is True
    second = lock.try_acquire("live", ttl_seconds=30)
    assert second is not None
    lock.release("live", second)


def test_hold_job_lock_context() -> None:
    lock = InMemoryJobLock()
    with hold_job_lock(lock, "post_match", ttl_seconds=10) as token:
        assert token is not None
        with hold_job_lock(lock, "post_match", ttl_seconds=10) as busy:
            assert busy is None
    again = lock.try_acquire("post_match", ttl_seconds=10)
    assert again is not None


def test_beat_schedule_respects_enabled_flag() -> None:
    assert beat_schedule_entries(enabled=False) == {}
    schedule = beat_schedule_entries(enabled=True, live_interval=30)
    assert "sports-poll-live" in schedule
    assert schedule["sports-poll-live"]["task"] == "sports_data.poll_live_window"
    assert schedule["sports-poll-live"]["schedule"] == 30.0
    assert "sports-poll-pre" in schedule
    assert "sports-poll-post" in schedule
    assert "sports-poll-late" in schedule
