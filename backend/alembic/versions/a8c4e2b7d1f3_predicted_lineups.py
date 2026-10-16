"""FotMob probable lineup snapshots.

Revision ID: a8c4e2b7d1f3
Revises: d3b7e1a9c4f2
Create Date: 2026-10-16 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8c4e2b7d1f3"
down_revision: str | Sequence[str] | None = "d3b7e1a9c4f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fotmob_fixture_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fotmob_match_id", sa.Integer(), nullable=False),
        sa.Column("home_name", sa.String(length=160), nullable=False),
        sa.Column("away_name", sa.String(length=160), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_fotmob_fixture_links_fixture_id_fixtures"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fotmob_fixture_links")),
        sa.UniqueConstraint("fixture_id", name="uq_fotmob_fixture_links_fixture_id"),
        sa.UniqueConstraint("fotmob_match_id", name="uq_fotmob_fixture_links_fotmob_match_id"),
    )
    op.create_table(
        "predicted_lineup_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fotmob_match_id", sa.Integer(), nullable=False),
        sa.Column("lineup_type", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("reliability", sa.String(length=32), nullable=False),
        sa.Column(
            "warning_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("home_formation", sa.String(length=32), nullable=True),
        sa.Column("away_formation", sa.String(length=32), nullable=True),
        sa.Column("home_coach", sa.String(length=160), nullable=True),
        sa.Column("away_coach", sa.String(length=160), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_predicted_lineup_snapshots_fixture_id_fixtures"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predicted_lineup_snapshots")),
    )
    op.create_index(
        op.f("ix_predicted_lineup_snapshots_fixture_id"),
        "predicted_lineup_snapshots",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_predicted_lineup_snapshots_fetched_at"),
        "predicted_lineup_snapshots",
        ["fetched_at"],
        unique=False,
    )
    op.create_table(
        "predicted_lineup_players",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("shirt_number", sa.Integer(), nullable=True),
        sa.Column("fotmob_player_id", sa.Integer(), nullable=True),
        sa.Column("is_starter", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "is_unavailable",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("unavailability_type", sa.String(length=32), nullable=True),
        sa.Column("unavailability_label", sa.String(length=160), nullable=True),
        sa.Column(
            "blocks_selection",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("grid", sa.String(length=16), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_predicted_lineup_players_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_predicted_lineup_players_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["predicted_lineup_snapshots.id"],
            name=op.f("fk_predicted_lineup_players_snapshot_id_predicted_lineup_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predicted_lineup_players")),
    )
    op.create_index(
        op.f("ix_predicted_lineup_players_snapshot_id"),
        "predicted_lineup_players",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_predicted_lineup_players_athlete_id"),
        "predicted_lineup_players",
        ["athlete_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_predicted_lineup_players_athlete_id"),
        table_name="predicted_lineup_players",
    )
    op.drop_index(
        op.f("ix_predicted_lineup_players_snapshot_id"),
        table_name="predicted_lineup_players",
    )
    op.drop_table("predicted_lineup_players")
    op.drop_index(
        op.f("ix_predicted_lineup_snapshots_fetched_at"),
        table_name="predicted_lineup_snapshots",
    )
    op.drop_index(
        op.f("ix_predicted_lineup_snapshots_fixture_id"),
        table_name="predicted_lineup_snapshots",
    )
    op.drop_table("predicted_lineup_snapshots")
    op.drop_table("fotmob_fixture_links")
