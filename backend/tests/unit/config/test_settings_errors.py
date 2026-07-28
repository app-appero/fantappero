"""Missing or malformed configuration fails with actionable messages."""

from __future__ import annotations

import pytest

from config.settings.loader import ConfigurationError, get_api_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_missing_database_url_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    with pytest.raises(ConfigurationError) as exc:
        get_api_settings()

    message = str(exc.value)
    assert "DATABASE_URL" in message or "database_url" in message
    assert "Missing required" in message or "validation failed" in message.lower()


def test_missing_redis_url_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://fantappero:secret@127.0.0.1:5432/fantappero",
    )
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ConfigurationError) as exc:
        get_api_settings()

    message = str(exc.value)
    assert "REDIS_URL" in message or "redis_url" in message


def test_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "verbose")

    with pytest.raises(ConfigurationError):
        get_api_settings()


def test_configuration_error_does_not_leak_dsn_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "development")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://fantappero:super_secret_pw@127.0.0.1:5432/fantappero",
    )
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ConfigurationError) as exc:
        get_api_settings()

    message = str(exc.value)
    assert "super_secret_pw" not in message
