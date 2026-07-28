"""Liveness vs readiness when dependencies are unavailable."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live_ok_even_when_deps_unreachable(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://fantappero:bad@127.0.0.1:1/fantappero")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    response = client.get("/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["probe"] == "live"


def test_ready_errors_when_configured_deps_unreachable(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://fantappero:bad@127.0.0.1:1/fantappero")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["probe"] == "ready"
    assert "postgres" in body["failed"]
    assert "redis" in body["failed"]


def test_health_aliases_readiness(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://fantappero:bad@127.0.0.1:1/fantappero")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["probe"] == "ready"


def test_ready_ok_without_deps() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["probe"] == "ready"
    assert body["checks"]["postgres"]["status"] == "skipped"
