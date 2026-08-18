"""Fixtures for devtools integration tests — reuse database module engine."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from tests.integration.database.helpers import (
    create_engine_for_url,
    require_database_url,
    reset_to_base,
    upgrade_head,
)

from auth.dependencies import reset_db_cache
from config.settings.loader import reset_settings_cache


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


@pytest.fixture(autouse=True)
def _devtools_test_env(monkeypatch: pytest.MonkeyPatch, db_url: str) -> None:
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.delenv("BOOTSTRAP_OPERATOR_EMAIL", raising=False)
    reset_settings_cache()
    reset_db_cache()


@pytest.fixture()
def session(migrated_engine) -> Session:
    sess = Session(bind=migrated_engine)
    try:
        yield sess
    finally:
        sess.rollback()
        sess.close()
