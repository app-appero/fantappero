"""League configuration: competitions, draft state, audit (EP03-01).

Revision ID: e0f6a3b4c507
Revises: d9e5f2a3b406
Create Date: 2026-07-29 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e0f6a3b4c507"
down_revision: str | Sequence[str] | None = "d9e5f2a3b406"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

league_state = postgresql.ENUM(
    "draft",
    "active",
    name="league_state",
    create_type=False,
)
league_audit_action = postgresql.ENUM(
    "league_created",
    name="league_audit_action",
    create_type=False,
)

MVP_COMPETITION_ROWS = (
    (39, "Premier League", "England"),
    (140, "La Liga", "Spain"),
    (135, "Serie A", "Italy"),
    (78, "Bundesliga", "Germany"),
    (61, "Ligue 1", "France"),
)


def upgrade() -> None:
    league_state.create(op.get_bind(), checkfirst=True)
    league_audit_action.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "competitions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
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
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", name=op.f("uq_competitions_provider_id")),
    )

    competitions = sa.table(
        "competitions",
        sa.column("provider_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("country", sa.String),
    )
    op.bulk_insert(
        competitions,
        [
            {"provider_id": provider_id, "name": name, "country": country}
            for provider_id, name, country in MVP_COMPETITION_ROWS
        ],
    )

    op.add_column(
        "leagues",
        sa.Column("season_year", sa.Integer(), nullable=False, server_default="2025"),
    )
    op.add_column(
        "leagues",
        sa.Column(
            "state",
            league_state,
            nullable=False,
            server_default="draft",
        ),
    )
    op.alter_column("leagues", "season_year", server_default=None)

    op.create_table(
        "league_competitions",
        sa.Column("league_id", sa.Uuid(), nullable=False),
        sa.Column("competition_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_league_competitions_competition_id_competitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_league_competitions_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("league_id", "competition_id", name=op.f("pk_league_competitions")),
    )

    op.create_table(
        "league_audit_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
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
        sa.Column("league_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", league_audit_action, nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_league_audit_events_actor_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_league_audit_events_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_league_audit_events")),
    )
    op.create_index(
        op.f("ix_league_audit_events_actor_id"),
        "league_audit_events",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_league_audit_events_league_id"),
        "league_audit_events",
        ["league_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_league_audit_events_league_id"), table_name="league_audit_events")
    op.drop_index(op.f("ix_league_audit_events_actor_id"), table_name="league_audit_events")
    op.drop_table("league_audit_events")
    op.drop_table("league_competitions")
    op.drop_column("leagues", "state")
    op.drop_column("leagues", "season_year")
    op.drop_table("competitions")
    league_audit_action.drop(op.get_bind(), checkfirst=True)
    league_state.drop(op.get_bind(), checkfirst=True)
