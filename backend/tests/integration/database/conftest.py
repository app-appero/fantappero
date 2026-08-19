"""Fixtures for database integration tests."""

from __future__ import annotations

import pytest
from tests.integration.database.helpers import (
    create_engine_for_url,
    require_database_url,
    reset_to_base,
    upgrade_head,
)


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
