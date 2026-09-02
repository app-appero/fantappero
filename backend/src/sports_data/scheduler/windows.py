"""Match polling windows (pre / live / post / late) — EP04-06 / EP00-04."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

# Align with tools/api_quota_estimator/config/default.json windows.
PRE_LEAD = timedelta(hours=6)
LIVE_MAX_DURATION = timedelta(minutes=130)
POST_DURATION = timedelta(hours=2)
LATE_DURATION = timedelta(hours=72)

LIVE_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"})
FINISHED_STATUSES = frozenset({"FT", "AET", "PEN"})
PRE_STATUSES = frozenset({"NS", "TBD"})
TERMINAL_SKIP_STATUSES = frozenset({"CANC", "ABD", "AWD", "WO"})


class PollWindow(StrEnum):
    PRE_MATCH = "pre_match"
    LIVE = "live"
    POST_MATCH = "post_match"
    LATE_CORRECTIONS = "late_corrections"


def classify_fixture_window(
    *,
    status_short: str,
    kickoff_at: datetime | None,
    now: datetime | None = None,
) -> PollWindow | None:
    """Return the active polling window for a fixture, or ``None`` if out of scope."""
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    status = (status_short or "").strip().upper()
    if status in TERMINAL_SKIP_STATUSES:
        return None

    kickoff = _as_utc(kickoff_at)

    if status in LIVE_STATUSES:
        return PollWindow.LIVE

    if status in FINISHED_STATUSES:
        finished_at = _estimate_finished_at(kickoff, clock)
        age = clock - finished_at
        if age < timedelta(0):
            return PollWindow.POST_MATCH
        if age <= POST_DURATION:
            return PollWindow.POST_MATCH
        if age <= LATE_DURATION:
            return PollWindow.LATE_CORRECTIONS
        return None

    if status in PRE_STATUSES or status == "PST":
        if kickoff is None:
            return PollWindow.PRE_MATCH
        if clock >= kickoff:
            # Overdue kickoff still marked not started → treat as live catch-up.
            if clock - kickoff <= LIVE_MAX_DURATION:
                return PollWindow.LIVE
            return PollWindow.POST_MATCH
        if kickoff - clock <= PRE_LEAD:
            return PollWindow.PRE_MATCH
        return None

    # Unknown status: if kickoff is imminent or recent, be conservative.
    if kickoff is not None:
        if timedelta(0) <= kickoff - clock <= PRE_LEAD:
            return PollWindow.PRE_MATCH
        if timedelta(0) <= clock - kickoff <= LIVE_MAX_DURATION:
            return PollWindow.LIVE
    return None


def _estimate_finished_at(kickoff: datetime | None, now: datetime) -> datetime:
    if kickoff is None:
        return now
    return kickoff + LIVE_MAX_DURATION


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
