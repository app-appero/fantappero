"""AI assistant audit trail: ai_interactions (EP10-01).

Revision ID: 94321d5a16fa
Revises: 1abdd05156d8
Create Date: 2026-08-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "94321d5a16fa"
down_revision: str | Sequence[str] | None = "1abdd05156d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AI_ASSISTANT_FEATURE = postgresql.ENUM(
    "viceallenatore",
    "osservatore",
    "analista",
    name="ai_assistant_feature",
    create_type=False,
)
_AI_FEEDBACK_RATING = postgresql.ENUM(
    "up",
    "down",
    name="ai_feedback_rating",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    _AI_ASSISTANT_FEATURE.create(bind, checkfirst=True)
    _AI_FEEDBACK_RATING.create(bind, checkfirst=True)

    op.create_table(
        "ai_interactions",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("feature", _AI_ASSISTANT_FEATURE, nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_key", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("feedback_rating", _AI_FEEDBACK_RATING, nullable=True),
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_ai_interactions_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_ai_interactions_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_interactions")),
    )
    op.create_index("ix_ai_interactions_user_id", "ai_interactions", ["user_id"])
    op.create_index("ix_ai_interactions_league_id", "ai_interactions", ["league_id"])
    op.create_index("ix_ai_interactions_feature", "ai_interactions", ["feature"])


def downgrade() -> None:
    op.drop_index("ix_ai_interactions_feature", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_league_id", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_user_id", table_name="ai_interactions")
    op.drop_table("ai_interactions")
    bind = op.get_bind()
    _AI_FEEDBACK_RATING.drop(bind, checkfirst=True)
    _AI_ASSISTANT_FEATURE.drop(bind, checkfirst=True)
