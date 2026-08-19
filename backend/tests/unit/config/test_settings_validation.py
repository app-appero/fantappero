"""Valid minimal configuration loads under the test profile."""

from __future__ import annotations

import pytest

from config.settings.loader import (
    get_api_settings,
    get_worker_settings,
    reset_settings_cache,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    for key in (
        "DATABASE_URL",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "API_FOOTBALL_KEY",
        "APISPORTS_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_api_settings_minimal_valid_in_test_profile() -> None:
    settings = get_api_settings()
    assert settings.fantappero_env.value == "test"
    assert settings.database_url is None
    assert settings.redis_url is None


def test_worker_settings_minimal_valid_in_test_profile() -> None:
    settings = get_worker_settings()
    assert settings.fantappero_env.value == "test"
    assert settings.resolved_broker_url().startswith("redis://")
    assert settings.resolved_result_backend().startswith("redis://")


def test_strict_profile_accepts_complete_infra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "development")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero",
    )
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
    reset_settings_cache()

    api = get_api_settings()
    worker = get_worker_settings()
    assert api.database_url is not None
    assert worker.celery_broker_url is not None
