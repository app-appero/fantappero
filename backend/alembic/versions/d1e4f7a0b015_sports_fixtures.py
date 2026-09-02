"""Fixtures, match events, official lineups and player match stats (EP04-05).

Revision ID: d1e4f7a0b015
Revises: c9d2e5f8a014
Create Date: 2026-08-05 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d1e4f7a0b015"
down_revision: str | Sequence[str] | None = "c9d2e5f8a014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fixtures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("sport_season_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("home_club_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("away_club_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_short", sa.String(length=16), nullable=False),
        sa.Column("status_elapsed", sa.Integer(), nullable=True),
        sa.Column("home_goals", sa.Integer(), nullable=True),
        sa.Column("away_goals", sa.Integer(), nullable=True),
        sa.Column("round_label", sa.String(length=64), nullable=True),
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
            ["away_club_id"],
            ["clubs.id"],
            name=op.f("fk_fixtures_away_club_id_clubs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["home_club_id"],
            ["clubs.id"],
            name=op.f("fk_fixtures_home_club_id_clubs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sport_season_id"],
            ["sport_seasons.id"],
            name=op.f("fk_fixtures_sport_season_id_sport_seasons"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fixtures")),
        sa.UniqueConstraint("provider_id", name="uq_fixtures_provider_id"),
    )
    op.create_index(op.f("ix_fixtures_sport_season_id"), "fixtures", ["sport_season_id"], unique=False)
    op.create_index(op.f("ix_fixtures_home_club_id"), "fixtures", ["home_club_id"], unique=False)
    op.create_index(op.f("ix_fixtures_away_club_id"), "fixtures", ["away_club_id"], unique=False)

    op.create_table(
        "match_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider_event_key", sa.String(length=256), nullable=False),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=True),
        sa.Column("related_athlete_provider_id", sa.Integer(), nullable=True),
        sa.Column("club_provider_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_detail", sa.String(length=64), nullable=True),
        sa.Column("scoring_kind", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'timeline'"), nullable=False),
        sa.Column("minute_elapsed", sa.Integer(), nullable=True),
        sa.Column("minute_extra", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column(
            "sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "anomaly_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_match_events_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_match_events_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_match_events_fixture_id_fixtures"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["related_athlete_id"],
            ["athletes.id"],
            name=op.f("fk_match_events_related_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_events")),
        sa.UniqueConstraint("provider_event_key", name="uq_match_events_provider_event_key"),
    )
    op.create_index(op.f("ix_match_events_fixture_id"), "match_events", ["fixture_id"], unique=False)
    op.create_index(op.f("ix_match_events_athlete_id"), "match_events", ["athlete_id"], unique=False)

    op.create_table(
        "official_lineups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("formation", sa.String(length=32), nullable=True),
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
            name=op.f("fk_official_lineups_club_id_clubs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_official_lineups_fixture_id_fixtures"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_official_lineups")),
        sa.UniqueConstraint("fixture_id", "club_id", name="uq_official_lineups_fixture_id_club_id"),
    )
    op.create_index(
        op.f("ix_official_lineups_fixture_id"),
        "official_lineups",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(op.f("ix_official_lineups_club_id"), "official_lineups", ["club_id"], unique=False)

    op.create_table(
        "official_lineup_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("lineup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=False),
        sa.Column("is_starter", sa.Boolean(), nullable=False),
        sa.Column("shirt_number", sa.Integer(), nullable=True),
        sa.Column("position_raw", sa.String(length=16), nullable=True),
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
            name=op.f("fk_official_lineup_entries_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lineup_id"],
            ["official_lineups.id"],
            name=op.f("fk_official_lineup_entries_lineup_id_official_lineups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_official_lineup_entries")),
        sa.UniqueConstraint(
            "lineup_id",
            "athlete_provider_id",
            name="uq_official_lineup_entries_lineup_id_athlete_provider_id",
        ),
    )
    op.create_index(
        op.f("ix_official_lineup_entries_lineup_id"),
        "official_lineup_entries",
        ["lineup_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_lineup_entries_athlete_id"),
        "official_lineup_entries",
        ["athlete_id"],
        unique=False,
    )

    op.create_table(
        "player_match_stats",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("athlete_provider_id", sa.Integer(), nullable=False),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("position_raw", sa.String(length=32), nullable=True),
        sa.Column("is_substitute", sa.Boolean(), nullable=True),
        sa.Column("provider_rating", sa.String(length=16), nullable=True),
        sa.Column(
            "stats_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("stats_hash", sa.String(length=64), nullable=False),
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
            name=op.f("fk_player_match_stats_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_player_match_stats_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_player_match_stats_fixture_id_fixtures"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_player_match_stats")),
        sa.UniqueConstraint(
            "fixture_id",
            "athlete_provider_id",
            name="uq_player_match_stats_fixture_id_athlete_provider_id",
        ),
    )
    op.create_index(
        op.f("ix_player_match_stats_fixture_id"),
        "player_match_stats",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_match_stats_athlete_id"),
        "player_match_stats",
        ["athlete_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_player_match_stats_athlete_id"), table_name="player_match_stats")
    op.drop_index(op.f("ix_player_match_stats_fixture_id"), table_name="player_match_stats")
    op.drop_table("player_match_stats")
    op.drop_index(op.f("ix_official_lineup_entries_athlete_id"), table_name="official_lineup_entries")
    op.drop_index(op.f("ix_official_lineup_entries_lineup_id"), table_name="official_lineup_entries")
    op.drop_table("official_lineup_entries")
    op.drop_index(op.f("ix_official_lineups_club_id"), table_name="official_lineups")
    op.drop_index(op.f("ix_official_lineups_fixture_id"), table_name="official_lineups")
    op.drop_table("official_lineups")
    op.drop_index(op.f("ix_match_events_athlete_id"), table_name="match_events")
    op.drop_index(op.f("ix_match_events_fixture_id"), table_name="match_events")
    op.drop_table("match_events")
    op.drop_index(op.f("ix_fixtures_away_club_id"), table_name="fixtures")
    op.drop_index(op.f("ix_fixtures_home_club_id"), table_name="fixtures")
    op.drop_index(op.f("ix_fixtures_sport_season_id"), table_name="fixtures")
    op.drop_table("fixtures")
