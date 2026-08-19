"""Dependency probes for Postgres and Redis used by /health."""

from __future__ import annotations

from typing import Any

from app.settings import database_url, redis_url


def check_postgres() -> dict[str, Any]:
    url = database_url()
    if not url:
        return {"configured": False, "status": "skipped"}
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return {"configured": True, "status": "ok"}
    except Exception as exc:  # noqa: BLE001 — surface probe failure to health
        return {"configured": True, "status": "error", "detail": type(exc).__name__}


def check_redis() -> dict[str, Any]:
    url = redis_url()
    if not url:
        return {"configured": False, "status": "skipped"}
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
        if client.ping() is not True:
            return {"configured": True, "status": "error", "detail": "ping_failed"}
        return {"configured": True, "status": "ok"}
    except Exception as exc:  # noqa: BLE001 — surface probe failure to health
        return {"configured": True, "status": "error", "detail": type(exc).__name__}


def aggregate_health() -> tuple[int, dict[str, Any]]:
    """Return HTTP status and body. Configured deps must be ok for 200."""
    postgres = check_postgres()
    redis_check = check_redis()
    checks = {"postgres": postgres, "redis": redis_check}

    failures = [
        name
        for name, result in checks.items()
        if result.get("configured") and result.get("status") != "ok"
    ]
    if failures:
        return 503, {"status": "error", "checks": checks, "failed": failures}
    return 200, {"status": "ok", "checks": checks}
