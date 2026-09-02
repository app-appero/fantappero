"""Fantasy european turns and min fixtures rule (EP06-01).

Revision ID: a0b1c2d3e070
Revises: a9d3e5f7b063
Create Date: 2026-08-12 09:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a0b1c2d3e070"
down_revision: str | Sequence[str] | None = "a9d3e5f7b063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "fantasy_turn_generated",
    "fantasy_turn_opened",
    "fantasy_turn_fixture_excluded",
    "fantasy_turn_cutoff_recalculated",
)

fantasy_turn_status = postgresql.ENUM(
    "scheduled",
    "open",
    "locked",
    "skipped",
    name="fantasy_turn_status",
    create_type=False,
)

fantasy_turn_kind = postgresql.ENUM(
    "weekend",
    "midweek",
    name="fantasy_turn_kind",
    create_type=False,
)

fantasy_round_fixture_reason = postgresql.ENUM(
    "window",
    "admin_include",
    name="fantasy_round_fixture_reason",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    fantasy_turn_status.create(op.get_bind(), checkfirst=True)
    fantasy_turn_kind.create(op.get_bind(), checkfirst=True)
    fantasy_round_fixture_reason.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "league_rules",
        sa.Column(
            "min_fixtures_per_round",
            sa.Integer(),
            nullable=False,
            server_default="25",
        ),
    )
    op.create_check_constraint(
        "ck_league_rules_min_fixtures_per_round",
        "league_rules",
        "min_fixtures_per_round BETWEEN 10 AND 40",
    )

    op.create_table(
        "fantasy_rounds",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("league_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("kind", fantasy_turn_kind, nullable=False),
        sa.Column("window_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            fantasy_turn_status,
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint("number >= 1", name="ck_fantasy_rounds_number"),
        sa.CheckConstraint(
            "window_end_at > window_start_at",
            name="ck_fantasy_rounds_window_order",
        ),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "number", name="uq_fantasy_rounds_league_number"),
    )
    op.create_index("ix_fantasy_rounds_league_id", "fantasy_rounds", ["league_id"])
    op.create_index("ix_fantasy_rounds_status", "fantasy_rounds", ["status"])
    op.create_index(
        "ix_fantasy_rounds_window",
        "fantasy_rounds",
        ["league_id", "window_start_at", "window_end_at"],
    )

    op.create_table(
        "fantasy_round_fixtures",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("round_id", sa.UUID(), nullable=False),
        sa.Column("league_id", sa.UUID(), nullable=False),
        sa.Column("fixture_id", sa.UUID(), nullable=False),
        sa.Column(
            "included_reason",
            fantasy_round_fixture_reason,
            nullable=False,
            server_default="window",
        ),
        sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("excluded_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["round_id"], ["fantasy_rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fixture_id"], ["fixtures.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["excluded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "round_id",
            "fixture_id",
            name="uq_fantasy_round_fixtures_round_fixture",
        ),
    )
    op.create_index(
        "ix_fantasy_round_fixtures_round_id",
        "fantasy_round_fixtures",
        ["round_id"],
    )
    op.create_index(
        "ix_fantasy_round_fixtures_league_id",
        "fantasy_round_fixtures",
        ["league_id"],
    )
    op.create_index(
        "ix_fantasy_round_fixtures_fixture_id",
        "fantasy_round_fixtures",
        ["fixture_id"],
    )
    op.create_index(
        "uq_fantasy_round_fixtures_active_league_fixture",
        "fantasy_round_fixtures",
        ["league_id", "fixture_id"],
        unique=True,
        postgresql_where=sa.text("excluded_at IS NULL"),
    )


def downgrade() -> None:
    # Support both the corrected per-league unique index and the earlier global one.
    op.execute("DROP INDEX IF EXISTS uq_fantasy_round_fixtures_active_league_fixture")
    op.execute("DROP INDEX IF EXISTS uq_fantasy_round_fixtures_active_fixture")
    op.execute("DROP INDEX IF EXISTS ix_fantasy_round_fixtures_fixture_id")
    op.execute("DROP INDEX IF EXISTS ix_fantasy_round_fixtures_league_id")
    op.execute("DROP INDEX IF EXISTS ix_fantasy_round_fixtures_round_id")
    op.execute("DROP TABLE IF EXISTS fantasy_round_fixtures")

    op.execute("DROP INDEX IF EXISTS ix_fantasy_rounds_window")
    op.execute("DROP INDEX IF EXISTS ix_fantasy_rounds_status")
    op.execute("DROP INDEX IF EXISTS ix_fantasy_rounds_league_id")
    op.execute("DROP TABLE IF EXISTS fantasy_rounds")

    op.execute(
        "ALTER TABLE league_rules DROP CONSTRAINT IF EXISTS ck_league_rules_min_fixtures_per_round"
    )
    op.execute("ALTER TABLE league_rules DROP COLUMN IF EXISTS min_fixtures_per_round")

    fantasy_round_fixture_reason.drop(op.get_bind(), checkfirst=True)
    fantasy_turn_kind.drop(op.get_bind(), checkfirst=True)
    fantasy_turn_status.drop(op.get_bind(), checkfirst=True)

    op.execute(
        sa.text(
            "DELETE FROM league_audit_events WHERE action::text IN "
            "('fantasy_turn_generated', 'fantasy_turn_opened', "
            "'fantasy_turn_fixture_excluded', 'fantasy_turn_cutoff_recalculated')"
        )
    )
