"""Liveness vs readiness probe helpers (no dependency on app package)."""

from __future__ import annotations

from typing import Any


def liveness() -> tuple[int, dict[str, Any]]:
    """Process is up — does not check external dependencies."""
    return 200, {"status": "ok", "probe": "live"}


def as_readiness(status_code: int, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Annotate an aggregate dependency check as a readiness probe."""
    return status_code, {**body, "probe": "ready"}
