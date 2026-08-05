"""Authorization integration test fixtures (EP02-03)."""

from __future__ import annotations

import os

import pytest
import redis
from fastapi.testclient import TestClient
from tests.integration.database.helpers import (
    create_engine_for_url,
    require_database_url,
    reset_to_base,
    upgrade_head,
)

from auth.dependencies import reset_db_cache
from config.settings.loader import reset_settings_cache
from mail.capture import clear_captured_emails


@pytest.fixture(scope="module")
def db_url() -> str:
    return require_database_url()


@pytest.fixture(scope="module")
def migrated_engine(db_url: str):
    reset_to_base(db_url)
    upgrade_head(db_url)
    engine = create_engine_for_url(db_url)
    yield engine
    engine.dispose()
    reset_to_base(db_url)


@pytest.fixture(scope="module")
def redis_url() -> str:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        pytest.skip("REDIS_URL not set — skipping authorization integration tests")
    return url


@pytest.fixture(autouse=True)
def _authorization_test_env(monkeypatch: pytest.MonkeyPatch, db_url: str, redis_url: str) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        os.environ.get("JWT_SECRET_KEY", "test_jwt_secret_for_pytest_only"),
    )
    reset_settings_cache()
    reset_db_cache()
    clear_captured_emails()


@pytest.fixture(autouse=True)
def _clear_auth_rate_limits(redis_url: str) -> None:
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    for key in client.scan_iter("auth:rl:*"):
        client.delete(key)


@pytest.fixture
def client(migrated_engine: object) -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
