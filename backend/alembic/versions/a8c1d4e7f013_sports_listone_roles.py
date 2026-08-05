"""Official listone role assignments and league overrides (EP04-04).

Revision ID: a8c1d4e7f013
Revises: f7a3b5c9d012
Create Date: 2026-08-04 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a8c1d4e7f013"
down_revision: str | Sequence[str] | None = "f7a3b5c9d012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "league_role_override_set",
    "league_role_override_cleared",
)

_PREVIOUS_AUDIT_ACTIONS = (
    "league_created",
    "league_rules_updated",
    "league_invite_created",
    "league_invite_revoked",
    "league_member_joined",
    "league_member_removed",
    "league_admin_transferred",
    "league_state_changed",
    "named_invite_created",
    "named_invite_accepted",
    "named_invite_declined",
    "named_invite_revoked",
    "league_calendar_generated",
    "league_calendar_confirmed",
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    op.execute("CREATE TYPE fantasy_role AS ENUM ('P', 'D', 'C', 'A');")
    fantasy_role = postgresql.ENUM(
        "P",
        "D",
        "C",
        "A",
        name="fantasy_role",
        create_type=False,
    )

    op.create_table(
        "role_assignments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("role", fantasy_role, nullable=False),
        sa.Column("provider_position_raw", sa.String(length=32), nullable=True),
        sa.Column("mapping_version", sa.String(length=32), nullable=False),
        sa.Column("squad_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("club_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            name=op.f("fk_role_assignments_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["squad_membership_id"],
            ["squad_memberships.id"],
            name=op.f("fk_role_assignments_squad_membership_id_squad_memberships"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name=op.f("fk_role_assignments_club_id_clubs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_assignments")),
        sa.UniqueConstraint(
            "athlete_id",
            "season_year",
            name="uq_role_assignments_athlete_id_season_year",
        ),
    )
    op.create_index(
        op.f("ix_role_assignments_athlete_id"),
        "role_assignments",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        "ix_role_assignments_season_year",
        "role_assignments",
        ["season_year"],
        unique=False,
    )

    op.create_table(
        "league_role_overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", fantasy_role, nullable=False),
        sa.Column("effective_from_round", sa.Integer(), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
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
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_league_role_overrides_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_league_role_overrides_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_league_role_overrides_actor_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_league_role_overrides")),
    )
    op.create_index(
        "ix_league_role_overrides_league_id",
        "league_role_overrides",
        ["league_id"],
        unique=False,
    )
    op.create_index(
        "ix_league_role_overrides_athlete_id",
        "league_role_overrides",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        "uq_league_role_overrides_active",
        "league_role_overrides",
        ["league_id", "athlete_id"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_league_role_overrides_active", table_name="league_role_overrides")
    op.drop_index("ix_league_role_overrides_athlete_id", table_name="league_role_overrides")
    op.drop_index("ix_league_role_overrides_league_id", table_name="league_role_overrides")
    op.drop_table("league_role_overrides")

    op.drop_index("ix_role_assignments_season_year", table_name="role_assignments")
    op.drop_index(op.f("ix_role_assignments_athlete_id"), table_name="role_assignments")
    op.drop_table("role_assignments")

    op.execute("DROP TYPE fantasy_role;")

    op.execute(
        "DELETE FROM league_audit_events WHERE action::text IN "
        "('league_role_override_set', 'league_role_override_cleared');"
    )
    op.execute("ALTER TYPE league_audit_action RENAME TO league_audit_action_old;")
    previous_actions = "', '".join(_PREVIOUS_AUDIT_ACTIONS)
    op.execute(f"CREATE TYPE league_audit_action AS ENUM ('{previous_actions}');")
    op.execute(
        """
        ALTER TABLE league_audit_events
        ALTER COLUMN action TYPE league_audit_action
        USING action::text::league_audit_action;
        """
    )
    op.execute("DROP TYPE league_audit_action_old;")
