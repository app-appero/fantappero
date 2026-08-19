"""League H2H calendar tables and audit actions (EP03-06).

Revision ID: e6f2a9b0c345
Revises: d5e1f8a0b234
Create Date: 2026-08-04 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6f2a9b0c345"
down_revision: str | Sequence[str] | None = "d5e1f8a0b234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "league_calendar_generated",
    "league_calendar_confirmed",
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
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    calendar_status = postgresql.ENUM(
        "draft",
        "confirmed",
        name="league_calendar_status",
        create_type=False,
    )
    calendar_format = postgresql.ENUM(
        "single_round_robin",
        name="league_calendar_format",
        create_type=False,
    )
    op.execute(
        "CREATE TYPE league_calendar_status AS ENUM ('draft', 'confirmed');"
    )
    op.execute(
        "CREATE TYPE league_calendar_format AS ENUM ('single_round_robin');"
    )

    op.create_table(
        "league_calendars",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            calendar_status,
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "format",
            calendar_format,
            server_default=sa.text("'single_round_robin'"),
            nullable=False,
        ),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column("participant_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("round_count", sa.Integer(), nullable=False),
        sa.Column("matchup_count", sa.Integer(), nullable=False),
        sa.Column("bye_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("participant_count BETWEEN 4 AND 10", name="ck_league_calendars_participants"),
        sa.CheckConstraint("round_count > 0", name="ck_league_calendars_round_count"),
        sa.CheckConstraint("matchup_count >= 0", name="ck_league_calendars_matchup_count"),
        sa.CheckConstraint("bye_count >= 0", name="ck_league_calendars_bye_count"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], name="fk_league_calendars_league_id_leagues", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_league_calendars"),
        sa.UniqueConstraint("league_id", name="uq_league_calendars_league_id"),
    )
    op.create_index("ix_league_calendars_league_id", "league_calendars", ["league_id"], unique=True)

    op.create_table(
        "league_calendar_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("calendar_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("is_bye", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("home_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("away_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("round_number > 0", name="ck_league_calendar_slots_round"),
        sa.CheckConstraint("slot_index >= 0", name="ck_league_calendar_slots_index"),
        sa.CheckConstraint(
            "("
            "is_bye = true AND home_membership_id IS NOT NULL AND away_membership_id IS NULL"
            ") OR ("
            "is_bye = false AND home_membership_id IS NOT NULL AND away_membership_id IS NOT NULL "
            "AND home_membership_id <> away_membership_id"
            ")",
            name="ck_league_calendar_slots_shape",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_id"],
            ["league_calendars.id"],
            name="fk_league_calendar_slots_calendar_id_league_calendars",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["home_membership_id"],
            ["league_memberships.id"],
            name="fk_league_calendar_slots_home_membership_id_league_memberships",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["away_membership_id"],
            ["league_memberships.id"],
            name="fk_league_calendar_slots_away_membership_id_league_memberships",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_league_calendar_slots"),
        sa.UniqueConstraint(
            "calendar_id",
            "round_number",
            "slot_index",
            name="uq_league_calendar_slots_round_slot",
        ),
    )
    op.create_index(
        "ix_league_calendar_slots_calendar_id",
        "league_calendar_slots",
        ["calendar_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_league_calendar_slots_calendar_id", table_name="league_calendar_slots")
    op.drop_table("league_calendar_slots")
    op.drop_index("ix_league_calendars_league_id", table_name="league_calendars")
    op.drop_table("league_calendars")
    op.execute("DROP TYPE league_calendar_format;")
    op.execute("DROP TYPE league_calendar_status;")

    actions = "', '".join(_NEW_AUDIT_ACTIONS)
    previous_actions = "', '".join(_PREVIOUS_AUDIT_ACTIONS)
    op.execute(f"DELETE FROM league_audit_events WHERE action::text IN ('{actions}');")
    op.execute("ALTER TYPE league_audit_action RENAME TO league_audit_action_old;")
    op.execute(f"CREATE TYPE league_audit_action AS ENUM ('{previous_actions}');")
    op.execute(
        """
        ALTER TABLE league_audit_events
        ALTER COLUMN action TYPE league_audit_action
        USING action::text::league_audit_action;
        """
    )
    op.execute("DROP TYPE league_audit_action_old;")
