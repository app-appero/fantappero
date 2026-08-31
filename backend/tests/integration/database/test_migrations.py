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
        assert table_exists(engine, "league_rules")
        assert table_exists(engine, "league_invites")
        assert table_exists(engine, "named_league_invites")
        assert table_exists(engine, "league_calendars")
        assert table_exists(engine, "league_calendar_slots")
        assert table_exists(engine, "provider_snapshots")
        assert table_exists(engine, "clubs")
        assert table_exists(engine, "sport_seasons")
        assert table_exists(engine, "competition_season_clubs")
        assert table_exists(engine, "athletes")
        assert table_exists(engine, "squad_memberships")
        assert table_exists(engine, "transfers")
        assert table_exists(engine, "role_assignments")
        assert table_exists(engine, "league_role_overrides")
        assert table_exists(engine, "fixtures")
        assert table_exists(engine, "match_events")
        assert table_exists(engine, "official_lineups")
        assert table_exists(engine, "official_lineup_entries")
        assert table_exists(engine, "player_match_stats")
        assert table_exists(engine, "player_match_ratings")
        assert table_exists(engine, "sports_poll_runs")
        assert table_exists(engine, "lineup_submissions")
        assert table_exists(engine, "lineup_drafts")
        assert table_exists(engine, "notifications")
        assert table_exists(engine, "notification_preferences")
        assert table_exists(engine, "ai_interactions")
        assert table_exists(engine, "user_entitlements")
        assert table_exists(engine, "subscription_payments")
        assert table_exists(engine, "alembic_version")
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            named_statuses = (
                conn.execute(
                    text(
                        """
                    SELECT enumlabel
                    FROM pg_enum
                    JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                    WHERE pg_type.typname = 'named_invite_status'
                    ORDER BY enumsortorder
                    """
                    )
                )
                .scalars()
                .all()
            )
            calendar_statuses = (
                conn.execute(
                    text(
                        """
                    SELECT enumlabel
                    FROM pg_enum
                    JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                    WHERE pg_type.typname = 'league_calendar_status'
                    ORDER BY enumsortorder
                    """
                    )
                )
                .scalars()
                .all()
            )
            fantasy_roles = (
                conn.execute(
                    text(
                        """
                    SELECT enumlabel
                    FROM pg_enum
                    JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                    WHERE pg_type.typname = 'fantasy_role'
                    ORDER BY enumsortorder
                    """
                    )
                )
                .scalars()
                .all()
            )
            # Head aggiornata da EP13-P02 (b4d7e2f9c118, Fantapunti in
            # classifica), EP13-P03 (c5e8a1f3d229, mappatura giornata →
            # finestra europea), EP13-P05 (d6f9a3b1c247, tracciabilità
            # formazione automatica IA), EP13-P04 live fix (a1c4f6e9b382,
            # venue/arbitro/logo squadra/allenatore), EP13-P04-quinquies
            # (c7f2a4d6e831, foto giocatore dal provider) ed
            # EP-turni-copertura (d8e3b5f7c962, soglia copertura formazione) ed
            # EP-turni-automazione (e2f5a8c1b374, margine di preavviso del lock).
            assert version == "e2f5a8c1b374"
        assert named_statuses == ["pending", "accepted", "declined", "revoked", "expired"]
        assert calendar_statuses == ["draft", "confirmed"]
        assert fantasy_roles == ["P", "D", "C", "A"]
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
