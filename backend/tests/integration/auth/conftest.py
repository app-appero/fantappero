"""Fixtures for auth integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.database.helpers import (
    create_engine_for_url,
    require_database_url,
    reset_to_base,
    upgrade_head,
)

from app import deps_auth
from app.deps_auth import reset_auth_deps_cache
from app.deps_db import reset_db_cache
from app.main import app
from auth.rate_limit import MemoryRateLimiter
from config.settings.loader import reset_settings_cache


@pytest.fixture(scope="module")
def db_url() -> str:
    return require_database_url()


@pytest.fixture(scope="module")
def auth_engine(db_url: str):
    reset_to_base(db_url)
    upgrade_head(db_url)
    engine = create_engine_for_url(db_url)
    yield engine
    engine.dispose()
    reset_to_base(db_url)


@pytest.fixture(scope="module")
def session_factory(auth_engine):
    return sessionmaker(bind=auth_engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _bind_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    reset_settings_cache()
    reset_db_cache()
    reset_auth_deps_cache()


@pytest.fixture
def rate_limiter() -> MemoryRateLimiter:
    return MemoryRateLimiter()


@pytest.fixture
def client(rate_limiter: MemoryRateLimiter) -> TestClient:
    app.dependency_overrides[deps_auth.get_rate_limiter] = lambda: rate_limiter
    yield TestClient(app)
    app.dependency_overrides.pop(deps_auth.get_rate_limiter, None)


@pytest.fixture
def db(session_factory) -> Session:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
