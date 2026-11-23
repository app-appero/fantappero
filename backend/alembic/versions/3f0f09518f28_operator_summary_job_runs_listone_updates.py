"""Riepilogo del pannello operatore: esito dei giri dei job e aggiornamenti del listone (1.4).

- ``system_job_runs``: una riga per ogni giro finito di un job periodico, ``ok`` o ``failed``
  con il motivo. Il worker tiene la tabella piccola (ultimi giri per job, errori per 30 giorni).
- ``listone_updates``: una riga per ogni aggiornamento riuscito del listone (data, autore,
  da dove e quanti calciatori entrati, usciti o cambiati), tenuta per sempre.

Decisione di Rosario del 22/11 («Da guardare» del Riepilogo). Solo due tabelle nuove: il
downgrade le toglie senza toccare il resto. Nascono vuote.

Revision ID: 3f0f09518f28
Revises: 70b4367fdb66
Create Date: 2026-11-23 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3f0f09518f28"
down_revision: str | Sequence[str] | None = "70b4367fdb66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "system_job_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("job_key", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("outcome IN ('ok', 'failed')", name=op.f("ck_system_job_runs_outcome")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_job_runs")),
    )
    op.create_index(
        "ix_system_job_runs_job_key_started_at",
        "system_job_runs",
        ["job_key", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_system_job_runs_outcome_started_at",
        "system_job_runs",
        ["outcome", "started_at"],
        unique=False,
    )

    op.create_table(
        "listone_updates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_display_name", sa.String(length=120), nullable=True),
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("league_name", sa.String(length=120), nullable=True),
        sa.Column("added", sa.Integer(), nullable=False),
        sa.Column("removed", sa.Integer(), nullable=False),
        sa.Column("changed", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "kind IN ('refresh', 'roles_from_provider', 'roles_restored')",
            name=op.f("ck_listone_updates_kind"),
        ),
        sa.CheckConstraint(
            "source IN ('operator', 'league')", name=op.f("ck_listone_updates_source")
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_listone_updates_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_listone_updates_league_id_leagues"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listone_updates")),
    )
    op.create_index(
        "ix_listone_updates_created_at", "listone_updates", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_listone_updates_created_at", table_name="listone_updates")
    op.drop_table("listone_updates")
    op.drop_index("ix_system_job_runs_outcome_started_at", table_name="system_job_runs")
    op.drop_index("ix_system_job_runs_job_key_started_at", table_name="system_job_runs")
    op.drop_table("system_job_runs")
