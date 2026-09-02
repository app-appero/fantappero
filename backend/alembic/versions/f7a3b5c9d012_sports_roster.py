"""Athletes, squad memberships and transfers (EP04-03).

Revision ID: f7a3b5c9d012
Revises: b2c4d6e8f012
Create Date: 2026-08-04 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f7a3b5c9d012"
down_revision: str | Sequence[str] | None = "b2c4d6e8f012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "athletes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=160), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=True),
        sa.Column("last_name", sa.String(length=80), nullable=True),
        sa.Column("nationality", sa.String(length=80), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("height", sa.String(length=16), nullable=True),
        sa.Column("weight", sa.String(length=16), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("injured", sa.Boolean(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_athletes")),
        sa.UniqueConstraint("provider_id", name="uq_athletes_provider_id"),
    )

    op.create_table(
        "squad_memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sport_season_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shirt_number", sa.Integer(), nullable=True),
        sa.Column("provider_position_raw", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ended_at", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=16), server_default=sa.text("'squads'"), nullable=False),
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
            name=op.f("fk_squad_memberships_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_squad_memberships_club_id_clubs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sport_season_id"],
            ["sport_seasons.id"],
            name=op.f("fk_squad_memberships_sport_season_id_sport_seasons"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_squad_memberships")),
        sa.UniqueConstraint(
            "athlete_id",
            "club_id",
            "sport_season_id",
            name="uq_squad_memberships_athlete_id_club_id_sport_season_id",
        ),
    )
    op.create_index(
        op.f("ix_squad_memberships_athlete_id"),
        "squad_memberships",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_squad_memberships_club_id"),
        "squad_memberships",
        ["club_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_squad_memberships_sport_season_id"),
        "squad_memberships",
        ["sport_season_id"],
        unique=False,
    )

    op.create_table(
        "transfers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("from_club_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_club_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transfer_type", sa.String(length=64), nullable=False),
        sa.Column(
            "requires_admin_review",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("provider_key", sa.String(length=128), nullable=False),
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
            name=op.f("fk_transfers_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_club_id"],
            ["clubs.id"],
            name=op.f("fk_transfers_from_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_club_id"],
            ["clubs.id"],
            name=op.f("fk_transfers_to_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfers")),
        sa.UniqueConstraint("provider_key", name="uq_transfers_provider_key"),
    )
    op.create_index(
        op.f("ix_transfers_athlete_id"),
        "transfers",
        ["athlete_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transfers_athlete_id"), table_name="transfers")
    op.drop_table("transfers")
    op.drop_index(op.f("ix_squad_memberships_sport_season_id"), table_name="squad_memberships")
    op.drop_index(op.f("ix_squad_memberships_club_id"), table_name="squad_memberships")
    op.drop_index(op.f("ix_squad_memberships_athlete_id"), table_name="squad_memberships")
    op.drop_table("squad_memberships")
    op.drop_table("athletes")
