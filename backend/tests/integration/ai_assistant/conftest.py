"""AI assistant integration fixtures (EP10-01) — same stack as market/notifications."""

from __future__ import annotations

import os

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.integration.database.helpers import (
    create_engine_for_url,
    require_database_url,
    reset_to_base,
    upgrade_head,
)

from auth.dependencies import reset_db_cache
from config.settings.loader import reset_settings_cache
from database.session import create_session_factory
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
        pytest.skip("REDIS_URL not set — skipping ai_assistant integration tests")
    return url


@pytest.fixture(autouse=True)
def _ai_assistant_test_env(monkeypatch: pytest.MonkeyPatch, db_url: str, redis_url: str) -> None:
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


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    # Depends on migrated_engine even though unused directly: it is what
    # triggers the module-scoped reset-to-base / upgrade-head around this
    # file's tests. Without it, tests using only db_session (no `client`)
    # would run against whatever schema/data state happened to be left over.
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
