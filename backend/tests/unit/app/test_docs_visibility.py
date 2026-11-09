"""Swagger/ReDoc/OpenAPI are reachable only in development/test (security review).

Serving them without auth in staging/production hands anyone the full API shape
(every route, including admin ones) for free reconnaissance.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


def _reload_main_with_env(monkeypatch: pytest.MonkeyPatch, env: str) -> object:
    monkeypatch.setenv("FANTAPPERO_ENV", env)
    import app.main as main_module

    return importlib.reload(main_module)


@pytest.fixture(autouse=True)
def _restore_test_app(monkeypatch: pytest.MonkeyPatch) -> None:
    # `app.main` is a module-global singleton other test files import; leave it reloaded
    # back to the "test" env so a later import elsewhere in the suite doesn't inherit
    # whatever env this file last reloaded it with.
    yield
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    import app.main as main_module

    importlib.reload(main_module)


@pytest.mark.parametrize("env", ["development", "test"])
def test_docs_are_served_in_development_and_test(monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    main_module = _reload_main_with_env(monkeypatch, env)
    client = TestClient(main_module.app)
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("env", ["staging", "production"])
def test_docs_are_hidden_in_staging_and_production(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    main_module = _reload_main_with_env(monkeypatch, env)
    client = TestClient(main_module.app)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
