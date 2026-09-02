"""Roster ownership intervals and turn snapshots (EP05-06).

Revision ID: a9d3e5f7b063
Revises: f8c2d4e6a052
Create Date: 2026-08-12 06:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9d3e5f7b063"
down_revision: str | Sequence[str] | None = "f8c2d4e6a052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "fantasy_roster_ownership_closed",
    "fantasy_roster_turn_snapshot_created",
)

roster_ownership_source = postgresql.ENUM(
    "manual",
    "csv_import",
    "admin",
    name="roster_ownership_source",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    roster_ownership_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "roster_ownership_intervals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("purchase_credits", sa.Integer(), nullable=False),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source",
            roster_ownership_source,
            server_default="manual",
            nullable=False,
        ),
        sa.CheckConstraint("slot_index >= 0", name=op.f("ck_roster_ownership_intervals_slot_index")),
        sa.CheckConstraint(
            "purchase_credits >= 0",
            name=op.f("ck_roster_ownership_intervals_purchase_credits"),
        ),
        sa.CheckConstraint(
            "released_at IS NULL OR released_at >= acquired_at",
            name=op.f("ck_roster_ownership_intervals_release_order"),
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_roster_ownership_intervals_athlete_id_athletes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_roster_ownership_intervals_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_roster_ownership_intervals_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_ownership_intervals")),
    )
    op.create_index(
        "ix_roster_ownership_intervals_league_id",
        "roster_ownership_intervals",
        ["league_id"],
    )
    op.create_index(
        "ix_roster_ownership_intervals_fantasy_team_id",
        "roster_ownership_intervals",
        ["fantasy_team_id"],
    )
    op.create_index(
        "ix_roster_ownership_intervals_athlete_id",
        "roster_ownership_intervals",
        ["athlete_id"],
    )
    op.create_index(
        "ix_roster_ownership_intervals_acquired_at",
        "roster_ownership_intervals",
        ["acquired_at"],
    )
    op.create_index(
        "uq_roster_ownership_intervals_active_athlete",
        "roster_ownership_intervals",
        ["league_id", "athlete_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
    )
    op.create_index(
        "uq_roster_ownership_intervals_active_slot",
        "roster_ownership_intervals",
        ["fantasy_team_id", "slot_index"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO roster_ownership_intervals (
                league_id,
                fantasy_team_id,
                athlete_id,
                slot_index,
                purchase_credits,
                acquired_at,
                released_at,
                source
            )
            SELECT
                s.league_id,
                s.fantasy_team_id,
                s.athlete_id,
                s.slot_index,
                COALESCE(s.purchase_credits, 0),
                COALESCE(s.updated_at, s.created_at, timezone('utc', now())),
                NULL,
                'manual'
            FROM fantasy_roster_slots AS s
            WHERE s.athlete_id IS NOT NULL
            """
        )
    )

    op.create_table(
        "roster_turn_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            "round_number >= 1",
            name=op.f("ck_roster_turn_snapshots_round_number"),
        ),
        sa.CheckConstraint(
            "entry_count >= 0",
            name=op.f("ck_roster_turn_snapshots_entry_count"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_roster_turn_snapshots_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_roster_turn_snapshots_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_turn_snapshots")),
        sa.UniqueConstraint(
            "league_id",
            "round_number",
            name=op.f("uq_roster_turn_snapshots_league_round"),
        ),
    )
    op.create_index(
        "ix_roster_turn_snapshots_league_id",
        "roster_turn_snapshots",
        ["league_id"],
    )

    op.create_table(
        "roster_turn_snapshot_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_credits", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=1), nullable=True),
        sa.CheckConstraint(
            "slot_index >= 0",
            name=op.f("ck_roster_turn_snapshot_entries_slot_index"),
        ),
        sa.CheckConstraint(
            "purchase_credits >= 0",
            name=op.f("ck_roster_turn_snapshot_entries_purchase_credits"),
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_roster_turn_snapshot_entries_athlete_id_athletes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_roster_turn_snapshot_entries_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["roster_turn_snapshots.id"],
            name=op.f("fk_roster_turn_snapshot_entries_snapshot_id_roster_turn_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_turn_snapshot_entries")),
        sa.UniqueConstraint(
            "snapshot_id",
            "fantasy_team_id",
            "slot_index",
            name=op.f("uq_roster_turn_snapshot_entries_snapshot_team_slot"),
        ),
    )
    op.create_index(
        "ix_roster_turn_snapshot_entries_snapshot_id",
        "roster_turn_snapshot_entries",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_roster_turn_snapshot_entries_fantasy_team_id",
        "roster_turn_snapshot_entries",
        ["fantasy_team_id"],
    )
    op.create_index(
        "ix_roster_turn_snapshot_entries_athlete_id",
        "roster_turn_snapshot_entries",
        ["athlete_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_roster_turn_snapshot_entries_athlete_id",
        table_name="roster_turn_snapshot_entries",
    )
    op.drop_index(
        "ix_roster_turn_snapshot_entries_fantasy_team_id",
        table_name="roster_turn_snapshot_entries",
    )
    op.drop_index(
        "ix_roster_turn_snapshot_entries_snapshot_id",
        table_name="roster_turn_snapshot_entries",
    )
    op.drop_table("roster_turn_snapshot_entries")

    op.drop_index("ix_roster_turn_snapshots_league_id", table_name="roster_turn_snapshots")
    op.drop_table("roster_turn_snapshots")

    op.drop_index(
        "uq_roster_ownership_intervals_active_slot",
        table_name="roster_ownership_intervals",
    )
    op.drop_index(
        "uq_roster_ownership_intervals_active_athlete",
        table_name="roster_ownership_intervals",
    )
    op.drop_index(
        "ix_roster_ownership_intervals_acquired_at",
        table_name="roster_ownership_intervals",
    )
    op.drop_index(
        "ix_roster_ownership_intervals_athlete_id",
        table_name="roster_ownership_intervals",
    )
    op.drop_index(
        "ix_roster_ownership_intervals_fantasy_team_id",
        table_name="roster_ownership_intervals",
    )
    op.drop_index(
        "ix_roster_ownership_intervals_league_id",
        table_name="roster_ownership_intervals",
    )
    op.drop_table("roster_ownership_intervals")

    roster_ownership_source.drop(op.get_bind(), checkfirst=True)

    op.execute(
        sa.text(
            "DELETE FROM league_audit_events "
            "WHERE action::text IN ("
            "'fantasy_roster_ownership_closed',"
            "'fantasy_roster_turn_snapshot_created'"
            ")"
        )
    )
