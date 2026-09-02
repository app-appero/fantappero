"""Player match statistical ratings (EP07-01).

Revision ID: f1a3c5e7b087
Revises: e0f2a4c6d086
Create Date: 2026-08-17 09:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f1a3c5e7b087"
down_revision: str | Sequence[str] | None = "e0f2a4c6d086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

fantasy_role = postgresql.ENUM(
    "P",
    "D",
    "C",
    "A",
    name="fantasy_role",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "player_match_ratings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=False),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("role", fantasy_role, nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("eligibility_reason", sa.String(length=64), nullable=False),
        sa.Column("base", sa.Float(), nullable=False),
        sa.Column("raw_before_clamp", sa.Float(), nullable=False),
        sa.Column("raw", sa.Float(), nullable=False),
        sa.Column("display", sa.Float(), nullable=True),
        sa.Column("stats_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "formula_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "input_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
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
        sa.CheckConstraint(
            "raw >= 3 AND raw <= 10",
            name=op.f("ck_player_match_ratings_raw_range"),
        ),
        sa.CheckConstraint(
            "display IS NULL OR (display >= 3 AND display <= 10)",
            name=op.f("ck_player_match_ratings_display_range"),
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_player_match_ratings_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_player_match_ratings_fixture_id_fixtures"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_player_match_ratings")),
        sa.UniqueConstraint(
            "fixture_id",
            "athlete_provider_id",
            "formula_version",
            name="uq_player_match_ratings_fixture_athlete_formula",
        ),
    )
    op.create_index(
        op.f("ix_player_match_ratings_fixture_id"),
        "player_match_ratings",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_match_ratings_athlete_id"),
        "player_match_ratings",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_match_ratings_formula_version"),
        "player_match_ratings",
        ["formula_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_player_match_ratings_formula_version"),
        table_name="player_match_ratings",
    )
    op.drop_index(
        op.f("ix_player_match_ratings_athlete_id"),
        table_name="player_match_ratings",
    )
    op.drop_index(
        op.f("ix_player_match_ratings_fixture_id"),
        table_name="player_match_ratings",
    )
    op.drop_table("player_match_ratings")
