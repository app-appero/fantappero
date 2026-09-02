"""Sports catalog tables: clubs, sport_seasons, competition_season_clubs (EP04-02).

Revision ID: b2c4d6e8f012
Revises: a1b2c3d4e567
Create Date: 2026-08-04 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b2c4d6e8f012"
down_revision: str | Sequence[str] | None = "a1b2c3d4e567"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clubs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("national", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clubs")),
        sa.UniqueConstraint("provider_id", name="uq_clubs_provider_id"),
    )

    op.create_table(
        "sport_seasons",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("competition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("coverage_events", sa.Boolean(), nullable=True),
        sa.Column("coverage_lineups", sa.Boolean(), nullable=True),
        sa.Column("coverage_statistics_players", sa.Boolean(), nullable=True),
        sa.Column("coverage_injuries", sa.Boolean(), nullable=True),
        sa.Column("coverage_predictions", sa.Boolean(), nullable=True),
        sa.Column("coverage_standings", sa.Boolean(), nullable=True),
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
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_sport_seasons_competition_id_competitions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sport_seasons")),
        sa.UniqueConstraint(
            "competition_id",
            "year",
            name="uq_sport_seasons_competition_id_year",
        ),
    )
    op.create_index(
        op.f("ix_sport_seasons_competition_id"),
        "sport_seasons",
        ["competition_id"],
        unique=False,
    )

    op.create_table(
        "competition_season_clubs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("sport_season_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_competition_season_clubs_club_id_clubs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sport_season_id"],
            ["sport_seasons.id"],
            name=op.f("fk_competition_season_clubs_sport_season_id_sport_seasons"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competition_season_clubs")),
        sa.UniqueConstraint(
            "sport_season_id",
            "club_id",
            name="uq_competition_season_clubs_sport_season_id_club_id",
        ),
    )
    op.create_index(
        op.f("ix_competition_season_clubs_sport_season_id"),
        "competition_season_clubs",
        ["sport_season_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competition_season_clubs_club_id"),
        "competition_season_clubs",
        ["club_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_competition_season_clubs_club_id"),
        table_name="competition_season_clubs",
    )
    op.drop_index(
        op.f("ix_competition_season_clubs_sport_season_id"),
        table_name="competition_season_clubs",
    )
    op.drop_table("competition_season_clubs")
    op.drop_index(op.f("ix_sport_seasons_competition_id"), table_name="sport_seasons")
    op.drop_table("sport_seasons")
    op.drop_table("clubs")
