"""Schedule overlay: disabling removes a job, editing the interval keeps last run."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from system_jobs.catalog import SYSTEM_JOBS_BY_KEY
from system_jobs.models import SystemJob
from system_jobs.schedule_sync import sync_schedule_entries
from system_jobs.service import _to_view


class _Interval:
    def __init__(self, seconds: float) -> None:
        self.run_every = timedelta(seconds=seconds)


def test_sync_removes_disabled_and_keeps_last_run_on_interval_change() -> None:
    kept = SimpleNamespace(
        task="sports_data.poll_live_window",
        schedule=_Interval(60),
        kwargs={},
        options={},
        last_run_at="kept",
    )
    removed = SimpleNamespace(task="old", schedule=_Interval(10), kwargs={}, options={})
    current = {"sports-poll-live": kept, "gone": removed}

    def make_entry(key: str, spec: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(
            task=spec["task"],
            schedule=_Interval(float(spec["schedule"])),  # type: ignore[arg-type]
            kwargs=dict(spec.get("kwargs") or {}),
            options=dict(spec.get("options") or {}),
            last_run_at=None,
        )

    sync_schedule_entries(
        current,
        {
            "sports-poll-live": {
                "task": "sports_data.poll_live_window",
                "schedule": 120.0,
                "options": {"expires": 120.0},
            }
        },
        make_entry=make_entry,
        interval_schedule=lambda run_every: _Interval(run_every.total_seconds()),
    )

    assert "gone" not in current
    assert current["sports-poll-live"] is kept
    assert kept.last_run_at == "kept"
    assert kept.schedule.run_every == timedelta(seconds=120)


def test_next_run_is_last_start_plus_interval_only_when_enabled() -> None:
    started = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    spec = SYSTEM_JOBS_BY_KEY["sports-poll-post"]
    running = SystemJob(
        key=spec.key,
        enabled=True,
        interval_seconds=600,
        last_started_at=started,
    )
    stopped = SystemJob(
        key=spec.key,
        enabled=False,
        interval_seconds=600,
        last_started_at=started,
    )
    assert _to_view(spec, running).next_run_at == started + timedelta(seconds=600)
    assert _to_view(spec, stopped).next_run_at is None
