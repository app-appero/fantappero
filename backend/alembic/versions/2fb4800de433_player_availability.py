"""Player availability from /injuries (OQ-11).

Revision ID: 2fb4800de433
Revises: e4a8c2d6f019
Create Date: 2026-09-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2fb4800de433"
down_revision: str | Sequence[str] | None = "e4a8c2d6f019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_availabilities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("club_provider_id", sa.Integer(), nullable=True),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fixture_provider_id", sa.Integer(), nullable=True),
        sa.Column("competition_provider_id", sa.Integer(), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("status_type_raw", sa.String(length=32), nullable=False),
        sa.Column("reason_raw", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("provider_key", sa.String(length=160), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("fk_player_availabilities_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_player_availabilities_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_player_availabilities_fixture_id_fixtures"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_player_availabilities")),
        sa.UniqueConstraint(
            "provider_key",
            name=op.f("uq_player_availabilities_provider_key"),
        ),
    )
    op.create_index(
        op.f("ix_player_availabilities_athlete_id"),
        "player_availabilities",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_availabilities_athlete_provider_id"),
        "player_availabilities",
        ["athlete_provider_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_availabilities_fixture_id"),
        "player_availabilities",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_availabilities_category"),
        "player_availabilities",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_player_availabilities_category"),
        table_name="player_availabilities",
    )
    op.drop_index(
        op.f("ix_player_availabilities_fixture_id"),
        table_name="player_availabilities",
    )
    op.drop_index(
        op.f("ix_player_availabilities_athlete_provider_id"),
        table_name="player_availabilities",
    )
    op.drop_index(
        op.f("ix_player_availabilities_athlete_id"),
        table_name="player_availabilities",
    )
    op.drop_table("player_availabilities")
