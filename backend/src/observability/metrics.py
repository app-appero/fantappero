"""In-process metrics for requests, errors, latencies, and jobs."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Counter:
    value: float = 0.0


@dataclass
class _Histogram:
    count: int = 0
    sum_seconds: float = 0.0
    max_seconds: float = 0.0

    def observe(self, seconds: float) -> None:
        self.count += 1
        self.sum_seconds += seconds
        if seconds > self.max_seconds:
            self.max_seconds = seconds


@dataclass
class MetricsRegistry:
    """Minimal process-local metrics (vendor-neutral; swap backend later)."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _counters: dict[tuple[str, tuple[tuple[str, str], ...]], _Counter] = field(
        default_factory=dict,
        repr=False,
    )
    _histograms: dict[tuple[str, tuple[tuple[str, str], ...]], _Histogram] = field(
        default_factory=dict,
        repr=False,
    )
    _gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = field(
        default_factory=dict,
        repr=False,
    )

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()

    def _label_key(self, labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
        if not labels:
            return ()
        return tuple(sorted((str(k), str(v)) for k, v in labels.items()))

    def incr(self, name: str, *, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        key = (name, self._label_key(labels))
        with self._lock:
            counter = self._counters.get(key)
            if counter is None:
                counter = _Counter()
                self._counters[key] = counter
            counter.value += amount

    def observe(
        self,
        name: str,
        seconds: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        key = (name, self._label_key(labels))
        with self._lock:
            hist = self._histograms.get(key)
            if hist is None:
                hist = _Histogram()
                self._histograms[key] = hist
            hist.observe(seconds)

    def set_gauge(self, name: str, value: float, *, labels: dict[str, str] | None = None) -> None:
        key = (name, self._label_key(labels))
        with self._lock:
            self._gauges[key] = value

    def get_counter(self, name: str, *, labels: dict[str, str] | None = None) -> float:
        key = (name, self._label_key(labels))
        with self._lock:
            counter = self._counters.get(key)
            return 0.0 if counter is None else counter.value

    def get_histogram(self, name: str, *, labels: dict[str, str] | None = None) -> dict[str, float]:
        key = (name, self._label_key(labels))
        with self._lock:
            hist = self._histograms.get(key)
            if hist is None:
                return {"count": 0.0, "sum_seconds": 0.0, "max_seconds": 0.0}
            return {
                "count": float(hist.count),
                "sum_seconds": hist.sum_seconds,
                "max_seconds": hist.max_seconds,
            }

    def get_gauge(self, name: str, *, labels: dict[str, str] | None = None) -> float:
        key = (name, self._label_key(labels))
        with self._lock:
            return float(self._gauges.get(key, 0.0))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = {
                f"{name}|{dict(labels)}" if labels else name: counter.value
                for (name, labels), counter in self._counters.items()
            }
            histograms = {
                f"{name}|{dict(labels)}" if labels else name: {
                    "count": hist.count,
                    "sum_seconds": hist.sum_seconds,
                    "max_seconds": hist.max_seconds,
                }
                for (name, labels), hist in self._histograms.items()
            }
            gauges = {
                f"{name}|{dict(labels)}" if labels else name: value
                for (name, labels), value in self._gauges.items()
            }
        return {"counters": counters, "histograms": histograms, "gauges": gauges}

    def render_prometheus(self) -> str:
        """Render a dependency-free Prometheus text snapshot.

        Histograms in this small registry do not retain buckets.  They are
        therefore exported as ``_count``, ``_sum`` and ``_max`` gauges instead
        of pretending to be Prometheus histograms.  This preserves the
        existing in-process contract while making short Beta/load-test runs
        externally observable.
        """
        with self._lock:
            counters = [
                (name, labels, counter.value) for (name, labels), counter in self._counters.items()
            ]
            histograms = [
                (name, labels, hist.count, hist.sum_seconds, hist.max_seconds)
                for (name, labels), hist in self._histograms.items()
            ]
            gauges = [(name, labels, value) for (name, labels), value in self._gauges.items()]

        lines: list[str] = []
        declared_types: set[str] = set()
        for name, labels, value in sorted(counters):
            metric_name = _prometheus_name(name)
            if metric_name not in declared_types:
                lines.append(f"# TYPE {metric_name} counter")
                declared_types.add(metric_name)
            lines.append(f"{metric_name}{_prometheus_labels(labels)} {value}")
        for name, labels, count, total, maximum in sorted(histograms):
            metric_name = _prometheus_name(name)
            for suffix, value in (("count", count), ("sum", total), ("max", maximum)):
                exported_name = f"{metric_name}_{suffix}"
                if exported_name not in declared_types:
                    lines.append(f"# TYPE {exported_name} gauge")
                    declared_types.add(exported_name)
                lines.append(f"{exported_name}{_prometheus_labels(labels)} {value}")
        for name, labels, value in sorted(gauges):
            metric_name = _prometheus_name(name)
            if metric_name not in declared_types:
                lines.append(f"# TYPE {metric_name} gauge")
                declared_types.add(metric_name)
            lines.append(f"{metric_name}{_prometheus_labels(labels)} {value}")
        return "\n".join(lines) + ("\n" if lines else "")


_INVALID_PROMETHEUS_NAME = re.compile(r"[^a-zA-Z0-9_:]")
_INVALID_PROMETHEUS_LABEL_NAME = re.compile(r"[^a-zA-Z0-9_]")


def _prometheus_name(value: str) -> str:
    sanitized = _INVALID_PROMETHEUS_NAME.sub("_", value)
    if not sanitized or sanitized[0].isdigit():
        return f"metric_{sanitized}"
    return sanitized


def _prometheus_label_name(value: str) -> str:
    sanitized = _INVALID_PROMETHEUS_LABEL_NAME.sub("_", value)
    if not sanitized or sanitized[0].isdigit():
        return f"label_{sanitized}"
    return sanitized


def _prometheus_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    rendered = []
    for raw_name, raw_value in labels:
        name = _prometheus_label_name(raw_name)
        value = raw_value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        rendered.append(f'{name}="{value}"')
    return "{" + ",".join(rendered) + "}"


# Metric names (stable contract for tests and future exporters).
HTTP_REQUESTS_TOTAL = "http_requests_total"
HTTP_REQUEST_ERRORS_TOTAL = "http_request_errors_total"
HTTP_REQUEST_DURATION_SECONDS = "http_request_duration_seconds"
JOBS_TOTAL = "jobs_total"
JOBS_FAILED_TOTAL = "jobs_failed_total"
JOB_DURATION_SECONDS = "job_duration_seconds"
QUEUE_DEPTH = "queue_depth"
# Provider / SPD adapter (EP04-01) — also defined on sports_data.provider.client
PROVIDER_REQUESTS_TOTAL = "provider_requests_total"
PROVIDER_REQUEST_ERRORS_TOTAL = "provider_request_errors_total"
PROVIDER_REQUEST_DURATION_SECONDS = "provider_request_duration_seconds"
PROVIDER_RETRIES_TOTAL = "provider_retries_total"
PROVIDER_RATE_LIMIT_REMAINING = "provider_rate_limit_remaining"
PROVIDER_SNAPSHOTS_STORED_TOTAL = "provider_snapshots_stored_total"
PROVIDER_SNAPSHOTS_DEDUPED_TOTAL = "provider_snapshots_deduped_total"


_metrics = MetricsRegistry()


def get_metrics() -> MetricsRegistry:
    return _metrics


def reset_metrics() -> None:
    _metrics.reset()


class Timer:
    """Context manager that records elapsed seconds into a histogram."""

    def __init__(
        self,
        metrics: MetricsRegistry,
        name: str,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        self._metrics = metrics
        self._name = name
        self._labels = labels
        self._start = 0.0
        self.elapsed = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.elapsed = time.perf_counter() - self._start
        self._metrics.observe(self._name, self.elapsed, labels=self._labels)
