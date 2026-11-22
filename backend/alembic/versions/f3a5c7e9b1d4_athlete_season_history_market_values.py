"""Storico stagionale dei calciatori, registro dell'import e Valore di mercato (release 1.3).

- ``athlete_season_stats``: una riga per calciatore + stagione + club + competizione; stagioni
  passate dal fornitore (``source = 'provider'``), stagione in corso dai nostri dati
  (``source = 'fantappero'``).
- ``athlete_season_import_fetches``: chiamate già fatte dall'import dello storico (riprendibile).
- ``athlete_market_values``: media stagionale e Valore materializzati per calciatore e stagione.

Solo tabelle nuove: il downgrade le toglie senza toccare il resto.

Revision ID: f3a5c7e9b1d4
Revises: e9b1d3f5a672
Create Date: 2026-11-22 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a5c7e9b1d4"
down_revision: str | Sequence[str] | None = "e9b1d3f5a672"
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


def _id_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "athlete_season_stats",
        _id_column(),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("club_provider_id", sa.Integer(), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("club_name", sa.String(length=120), nullable=True),
        sa.Column("competition_provider_id", sa.Integer(), nullable=False),
        sa.Column("competition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("competition_name", sa.String(length=120), nullable=True),
        sa.Column("appearances", sa.Integer(), nullable=True),
        sa.Column("lineups", sa.Integer(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("votes", sa.Integer(), nullable=True),
        sa.Column("fantasy_average", sa.Float(), nullable=True),
        sa.Column("goals", sa.Integer(), nullable=True),
        sa.Column("assists", sa.Integer(), nullable=True),
        sa.Column("goals_conceded", sa.Integer(), nullable=True),
        sa.Column("saves", sa.Integer(), nullable=True),
        sa.Column("penalties_saved", sa.Integer(), nullable=True),
        sa.Column("yellow_cards", sa.Integer(), nullable=True),
        sa.Column("red_cards", sa.Integer(), nullable=True),
        sa.Column("clean_sheets", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "source IN ('provider', 'fantappero')",
            name=op.f("ck_athlete_season_stats_source"),
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_athlete_season_stats_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_athlete_season_stats_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_athlete_season_stats_competition_id_competitions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["provider_snapshots.id"],
            name=op.f("fk_athlete_season_stats_snapshot_id_provider_snapshots"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_athlete_season_stats")),
        sa.UniqueConstraint(
            "athlete_provider_id",
            "season_year",
            "source",
            "club_provider_id",
            "competition_provider_id",
            name="uq_athlete_season_stats_row",
        ),
    )
    op.create_index(
        op.f("ix_athlete_season_stats_athlete_id"),
        "athlete_season_stats",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        "ix_athlete_season_stats_season_year_source",
        "athlete_season_stats",
        ["season_year", "source"],
        unique=False,
    )

    op.create_table(
        "athlete_season_import_fetches",
        _id_column(),
        sa.Column("request_key", sa.String(length=96), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("competition_provider_id", sa.Integer(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("page_total", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["provider_snapshots.id"],
            name=op.f("fk_athlete_season_import_fetches_snapshot_id_provider_snapshots"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_athlete_season_import_fetches")),
        sa.UniqueConstraint("request_key", name="uq_athlete_season_import_fetches_request_key"),
    )
    op.create_index(
        "ix_athlete_season_import_fetches_season_year_kind",
        "athlete_season_import_fetches",
        ["season_year", "kind"],
        unique=False,
    )

    op.create_table(
        "athlete_market_values",
        _id_column(),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("role", fantasy_role, nullable=False),
        sa.Column("value_index", sa.Float(), nullable=False),
        sa.Column("reference_value", sa.Float(), nullable=False),
        sa.Column("season_average", sa.Float(), nullable=True),
        sa.Column("season_average_year", sa.Integer(), nullable=True),
        sa.Column(
            "season_average_is_current",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("current_votes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_athlete_market_values_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_athlete_market_values")),
        sa.UniqueConstraint(
            "athlete_id",
            "season_year",
            name="uq_athlete_market_values_athlete_id_season_year",
        ),
    )
    op.create_index(
        "ix_athlete_market_values_season_year",
        "athlete_market_values",
        ["season_year"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_athlete_market_values_season_year", table_name="athlete_market_values")
    op.drop_table("athlete_market_values")
    op.drop_index(
        "ix_athlete_season_import_fetches_season_year_kind",
        table_name="athlete_season_import_fetches",
    )
    op.drop_table("athlete_season_import_fetches")
    op.drop_index("ix_athlete_season_stats_season_year_source", table_name="athlete_season_stats")
    op.drop_index(op.f("ix_athlete_season_stats_athlete_id"), table_name="athlete_season_stats")
    op.drop_table("athlete_season_stats")
