"""Valid minimal configuration loads under the test profile."""

from __future__ import annotations

import pytest

from config.settings.loader import (
    ConfigurationError,
    get_api_settings,
    get_worker_settings,
    reset_settings_cache,
)


def _set_minimal_strict_infra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero",
    )
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")


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
        # The surrounding shell (local dev, CI) commonly exports these for the rest of the
        # suite; clear them so this file's own assertions about the default values hold.
        "JWT_SECRET_KEY",
        "BILLING_WEBHOOK_SECRET",
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


def test_development_keeps_working_with_default_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh checkout boots without anyone having to invent secrets for it."""
    monkeypatch.setenv("FANTAPPERO_ENV", "development")
    _set_minimal_strict_infra(monkeypatch)
    reset_settings_cache()

    settings = get_api_settings()
    assert settings.resolved_jwt_secret() == "fantappero_local_jwt_dev_only_change_in_production"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_staging_and_production_reject_the_default_jwt_secret(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", env)
    _set_minimal_strict_infra(monkeypatch)
    reset_settings_cache()

    with pytest.raises(ConfigurationError, match="JWT_SECRET_KEY"):
        get_api_settings()


@pytest.mark.parametrize("env", ["staging", "production"])
def test_staging_and_production_reject_the_default_billing_webhook_secret(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", env)
    _set_minimal_strict_infra(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "a-real-production-secret-value")
    reset_settings_cache()

    with pytest.raises(ConfigurationError, match="BILLING_WEBHOOK_SECRET"):
        get_api_settings()


@pytest.mark.parametrize("env", ["staging", "production"])
def test_staging_and_production_accept_explicit_secrets(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", env)
    _set_minimal_strict_infra(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "a-real-production-secret-value")
    monkeypatch.setenv("BILLING_WEBHOOK_SECRET", "a-real-webhook-secret-value")
    reset_settings_cache()

    settings = get_api_settings()
    assert settings.resolved_jwt_secret() == "a-real-production-secret-value"
