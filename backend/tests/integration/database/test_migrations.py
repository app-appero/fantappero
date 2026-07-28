"""Alembic upgrade/downgrade and drift integration tests."""

from __future__ import annotations

from datetime import UTC

import pytest
from sqlalchemy import text
from tests.integration.database.helpers import (
    alembic_check,
    autogenerate_has_ops,
    create_engine_for_url,
    reset_to_base,
    table_exists,
    upgrade_head,
)

from database.enums import FlagScope
from database.models.infrastructure import SystemFlag


@pytest.fixture()
def clean_db(db_url: str):
    reset_to_base(db_url)
    yield db_url
    reset_to_base(db_url)


def test_upgrade_from_empty_database(clean_db: str) -> None:
    upgrade_head(clean_db)
    engine = create_engine_for_url(clean_db)
    try:
        assert table_exists(engine, "system_flags")
        assert table_exists(engine, "alembic_version")
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "7f3a1c9e2b04"
    finally:
        engine.dispose()


def test_downgrade_removes_baseline_objects(clean_db: str) -> None:
    upgrade_head(clean_db)
    reset_to_base(clean_db)
    engine = create_engine_for_url(clean_db)
    try:
        assert not table_exists(engine, "system_flags")
        with engine.connect() as conn:
            enum_exists = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'flag_scope')")
            ).scalar_one()
        assert enum_exists is False
    finally:
        engine.dispose()


def test_consecutive_upgrades_are_idempotent(clean_db: str) -> None:
    upgrade_head(clean_db)
    upgrade_head(clean_db)
    check = alembic_check(clean_db)
    assert check.returncode == 0, check.stderr


def test_alembic_check_detects_no_drift_after_upgrade(clean_db: str) -> None:
    upgrade_head(clean_db)
    check = alembic_check(clean_db)
    assert check.returncode == 0, check.stderr


def test_autogenerate_produces_no_unexpected_ops(clean_db: str) -> None:
    upgrade_head(clean_db)
    assert autogenerate_has_ops(clean_db) is False


def test_utc_timestamps_and_constraints(migrated_engine) -> None:
    from sqlalchemy.orm import Session

    session = Session(bind=migrated_engine)
    try:
        flag = SystemFlag(key="maintenance_mode", value="off", scope=FlagScope.SYSTEM)
        session.add(flag)
        session.commit()
        session.refresh(flag)
        assert flag.created_at.tzinfo is not None
        assert flag.created_at.astimezone(UTC).tzinfo == UTC

        duplicate = SystemFlag(key="maintenance_mode", value="on", scope=FlagScope.TENANT)
        session.add(duplicate)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()
    finally:
        session.close()
