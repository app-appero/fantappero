"""Polling policy defaults aligned with EP00-04 plan (EP04-06)."""

from __future__ import annotations

from dataclasses import dataclass

from sports_data.scheduler.quota import QuotaMode, interval_seconds
from sports_data.scheduler.windows import PollWindow


@dataclass(frozen=True)
class WindowPolicy:
    """Base intervals (seconds) and lock TTL for one polling window."""

    window: PollWindow
    base_interval_seconds: int
    lock_ttl_seconds: int
    max_fixtures_per_run: int | None
    fetch_live_batch: bool
    fetch_events: bool
    fetch_lineups: bool
    fetch_players: bool
    events_criticality: str = "critical"
    lineups_criticality: str = "high"
    players_criticality: str = "critical"
    fixtures_criticality: str = "high"


# Frequencies from tools/api_quota_estimator/config/default.json
DEFAULT_POLICIES: dict[PollWindow, WindowPolicy] = {
    PollWindow.PRE_MATCH: WindowPolicy(
        window=PollWindow.PRE_MATCH,
        base_interval_seconds=900,
        lock_ttl_seconds=840,
        max_fixtures_per_run=45,
        fetch_live_batch=False,
        fetch_events=False,
        fetch_lineups=True,
        fetch_players=False,
        lineups_criticality="high",
    ),
    PollWindow.LIVE: WindowPolicy(
        window=PollWindow.LIVE,
        base_interval_seconds=60,
        lock_ttl_seconds=55,
        max_fixtures_per_run=45,
        fetch_live_batch=True,
        fetch_events=True,
        fetch_lineups=False,
        fetch_players=False,
    ),
    PollWindow.POST_MATCH: WindowPolicy(
        window=PollWindow.POST_MATCH,
        base_interval_seconds=600,
        lock_ttl_seconds=540,
        max_fixtures_per_run=45,
        fetch_live_batch=False,
        fetch_events=True,
        fetch_lineups=True,
        fetch_players=True,
        lineups_criticality="medium",
    ),
    PollWindow.LATE_CORRECTIONS: WindowPolicy(
        window=PollWindow.LATE_CORRECTIONS,
        base_interval_seconds=3600,
        lock_ttl_seconds=3300,
        max_fixtures_per_run=15,
        fetch_live_batch=False,
        fetch_events=True,
        fetch_lineups=False,
        fetch_players=True,
    ),
}


def policy_for(window: PollWindow) -> WindowPolicy:
    return DEFAULT_POLICIES[window]


def effective_interval_seconds(window: PollWindow, mode: QuotaMode) -> float:
    return interval_seconds(float(policy_for(window).base_interval_seconds), mode)


def beat_schedule_entries(
    *,
    enabled: bool,
    live_interval: int | None = None,
    pre_interval: int | None = None,
    post_interval: int | None = None,
    late_interval: int | None = None,
) -> dict[str, dict]:
    """Celery beat schedule keyed by human-readable names."""
    if not enabled:
        return {}
    live = live_interval or DEFAULT_POLICIES[PollWindow.LIVE].base_interval_seconds
    pre = pre_interval or DEFAULT_POLICIES[PollWindow.PRE_MATCH].base_interval_seconds
    post = post_interval or DEFAULT_POLICIES[PollWindow.POST_MATCH].base_interval_seconds
    late = late_interval or DEFAULT_POLICIES[PollWindow.LATE_CORRECTIONS].base_interval_seconds
    return {
        "sports-poll-live": {
            "task": "sports_data.poll_live_window",
            "schedule": float(live),
            "options": {"expires": float(live)},
        },
        "sports-poll-pre": {
            "task": "sports_data.poll_pre_match_window",
            "schedule": float(pre),
            "options": {"expires": float(pre)},
        },
        "sports-poll-post": {
            "task": "sports_data.poll_post_match_window",
            "schedule": float(post),
            "options": {"expires": float(post)},
        },
        "sports-poll-late": {
            "task": "sports_data.poll_late_corrections_window",
            "schedule": float(late),
            "options": {"expires": float(late)},
        },
    }
