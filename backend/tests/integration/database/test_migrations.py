"""Alembic upgrade/downgrade and drift integration tests."""

from __future__ import annotations

from datetime import UTC

import pytest
from sqlalchemy import text
from tests.integration.database.helpers import (
    alembic_check,
    autogenerate_has_ops,
    create_engine_for_url,
    downgrade_one,
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
            # Head aggiornata da 37c365bf2399 (review admin trasferimenti
            # Loan/N.D., OQ-12) — aggiornare questa costante ad ogni nuova
            # migrazione in coda.
            assert version == "37c365bf2399"
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


def test_last_migration_applies_cleanly_to_a_populated_database(clean_db: str) -> None:
    """D2: le migrazioni erano provate solo su database vuoto (nessuna riga).

    Qui si arriva a un passo dalla testa, si popola il database con dati
    realistici (utenti, leghe, rose validate, formazioni, risultati — lo
    stesso seed usato per le prove di carico EP12-03, non dati sintetici
    minimi), poi si applica l'ultima migrazione sopra quei dati reali. Un
    ALTER che si comporta bene su una tabella vuota può comunque fallire (o
    corrompere righe) quando la tabella contiene già dati — è esattamente il
    tipo di problema mai stato messo alla prova fino ad ora.
    """
    from sqlalchemy.orm import Session as OrmSession

    from database.session import create_session_factory
    from devtools.seed_performance_scenario import seed

    upgrade_head(clean_db)
    downgrade_one(clean_db)

    engine = create_engine_for_url(clean_db)
    try:
        session = create_session_factory(engine)()
        try:
            manifest = seed(session, user_count=2, password="MigrationTest!123")
        finally:
            session.close()
        assert len(manifest["users"]) == 2
        with engine.connect() as conn:
            user_count_before = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
            league_count_before = conn.execute(text("SELECT count(*) FROM leagues")).scalar_one()
    finally:
        engine.dispose()

    upgrade_head(clean_db)

    engine = create_engine_for_url(clean_db)
    try:
        with engine.connect() as conn:
            user_count_after = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
            league_count_after = conn.execute(text("SELECT count(*) FROM leagues")).scalar_one()
        # I dati inseriti prima dell'ultima migrazione devono sopravvivere
        # intatti — confronto relativo, non un numero assoluto: alcune
        # migrazioni inseriscono righe di bootstrap (es. operatore
        # piattaforma), quindi il totale assoluto non è stabile nel tempo.
        assert user_count_after == user_count_before
        assert league_count_after == league_count_before
    finally:
        engine.dispose()
    check = alembic_check(clean_db)
    assert check.returncode == 0, check.stderr


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
