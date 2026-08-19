"""Fantasy teams and roster slots with league exclusivity (EP05-01).

Revision ID: b8d4f1a2c019
Revises: a7c3e9f1b018
Create Date: 2026-08-10 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8d4f1a2c019"
down_revision: str | Sequence[str] | None = "a7c3e9f1b018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "fantasy_team_created",
    "fantasy_roster_slot_assigned",
    "fantasy_roster_slot_released",
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    op.create_table(
        "fantasy_teams",
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
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_fantasy_teams_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["league_memberships.id"],
            name=op.f("fk_fantasy_teams_membership_id_league_memberships"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fantasy_teams")),
        sa.UniqueConstraint("membership_id", name=op.f("uq_fantasy_teams_membership_id")),
        sa.UniqueConstraint(
            "league_id",
            "membership_id",
            name=op.f("uq_fantasy_teams_league_id_membership_id"),
        ),
    )
    op.create_index("ix_fantasy_teams_league_id", "fantasy_teams", ["league_id"], unique=False)

    op.create_table(
        "fantasy_roster_slots",
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
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("slot_index >= 0", name=op.f("ck_fantasy_roster_slots_slot_index")),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_fantasy_roster_slots_athlete_id_athletes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_fantasy_roster_slots_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_fantasy_roster_slots_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fantasy_roster_slots")),
        sa.UniqueConstraint(
            "fantasy_team_id",
            "slot_index",
            name=op.f("uq_fantasy_roster_slots_team_slot"),
        ),
    )
    op.create_index(
        "ix_fantasy_roster_slots_fantasy_team_id",
        "fantasy_roster_slots",
        ["fantasy_team_id"],
        unique=False,
    )
    op.create_index(
        "ix_fantasy_roster_slots_league_id",
        "fantasy_roster_slots",
        ["league_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fantasy_roster_slots_athlete_id"),
        "fantasy_roster_slots",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        "uq_fantasy_roster_slots_league_athlete",
        "fantasy_roster_slots",
        ["league_id", "athlete_id"],
        unique=True,
        postgresql_where=sa.text("athlete_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM league_audit_events
        WHERE action::text IN (
            'fantasy_team_created',
            'fantasy_roster_slot_assigned',
            'fantasy_roster_slot_released'
        );
        """
    )
    op.drop_index(
        "uq_fantasy_roster_slots_league_athlete",
        table_name="fantasy_roster_slots",
        postgresql_where=sa.text("athlete_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_fantasy_roster_slots_athlete_id"), table_name="fantasy_roster_slots")
    op.drop_index("ix_fantasy_roster_slots_league_id", table_name="fantasy_roster_slots")
    op.drop_index("ix_fantasy_roster_slots_fantasy_team_id", table_name="fantasy_roster_slots")
    op.drop_table("fantasy_roster_slots")
    op.drop_index("ix_fantasy_teams_league_id", table_name="fantasy_teams")
    op.drop_table("fantasy_teams")
