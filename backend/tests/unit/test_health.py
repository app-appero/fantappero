"""Smoke tests for the scaffold FastAPI health surface."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_ok() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "fantappero-api"


def test_health_ok_without_deps(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["probe"] == "ready"
    assert body["checks"]["postgres"]["status"] == "skipped"
    assert body["checks"]["redis"]["status"] == "skipped"


def test_health_errors_when_configured_deps_unreachable(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://fantappero:bad@127.0.0.1:1/fantappero")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["probe"] == "ready"
    assert "postgres" in body["failed"]
    assert "redis" in body["failed"]
