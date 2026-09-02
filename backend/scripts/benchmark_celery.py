"""Measure real broker/worker/result-backend latency for EP12-03."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.worker import celery_app
from config.settings.loader import get_api_settings

ALLOWED_TASKS = {
    "app.worker.ping",
    "fantasy_turns.ensure_upcoming",
    "sports_data.poll_live_window",
}


def _guard() -> None:
    settings = get_api_settings()
    parsed = make_url(settings.database_url or "")
    if (
        os.getenv("PERFORMANCE_SEED_CONFIRM") != "isolated-performance-only"
        or parsed.host != "postgres-perf"
        or parsed.database != "fantappero_performance"
    ):
        raise SystemExit("Refusing Celery benchmark outside the isolated performance profile.")


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=sorted(ALLOWED_TASKS), required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--p95-ms", type=float, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 1 <= args.count <= 500:
        parser.error("--count must be between 1 and 500")
    _guard()

    submitted: list[tuple[object, float]] = []
    for _index in range(args.count):
        started = time.perf_counter()
        submitted.append((celery_app.send_task(args.task), started))

    durations_ms: list[float] = []
    errors: list[str] = []
    sample_result: object | None = None
    for result, started in submitted:
        try:
            value = result.get(timeout=args.timeout)
            sample_result = value if sample_result is None else sample_result
            durations_ms.append((time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001 -- report queue/worker failures
            errors.append(type(exc).__name__)

    p95_ms = _percentile(durations_ms, 0.95) if durations_ms else float("inf")
    summary = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "task": args.task,
        "submitted": args.count,
        "completed": len(durations_ms),
        "failed": len(errors),
        "latencyMs": {
            "min": min(durations_ms) if durations_ms else None,
            "p50": _percentile(durations_ms, 0.50) if durations_ms else None,
            "p95": p95_ms if durations_ms else None,
            "max": max(durations_ms) if durations_ms else None,
        },
        "thresholdP95Ms": args.p95_ms,
        "thresholdPassed": not errors and p95_ms < args.p95_ms,
        "sampleResult": sample_result,
        "errorTypes": sorted(set(errors)),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["thresholdPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
