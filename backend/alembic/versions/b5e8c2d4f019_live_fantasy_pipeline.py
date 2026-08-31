"""League-scoped ratings and automatic fantasy finalization support.

Revision ID: b5e8c2d4f019
Revises: a1c4f6e9b382
Create Date: 2026-08-28 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5e8c2d4f019"
down_revision: str | Sequence[str] | None = "a1c4f6e9b382"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing global snapshots remain valid (league_id NULL). New live
    # calculations persist one snapshot per league so minutes-threshold rules
    # cannot overwrite another league's result for the same real fixture.
    op.add_column("player_match_ratings", sa.Column("league_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_player_match_ratings_league_id_leagues"),
        "player_match_ratings",
        "leagues",
        ["league_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_player_match_ratings_league_id"),
        "player_match_ratings",
        ["league_id"],
        unique=False,
    )
    op.drop_constraint(
        "uq_player_match_ratings_fixture_athlete_formula",
        "player_match_ratings",
        type_="unique",
    )
    op.create_index(
        "uq_player_match_ratings_global_fixture_athlete_formula",
        "player_match_ratings",
        ["fixture_id", "athlete_provider_id", "formula_version"],
        unique=True,
        postgresql_where=sa.text("league_id IS NULL"),
    )
    op.create_index(
        "uq_player_match_ratings_league_fixture_athlete_formula",
        "player_match_ratings",
        ["league_id", "fixture_id", "athlete_provider_id", "formula_version"],
        unique=True,
        postgresql_where=sa.text("league_id IS NOT NULL"),
    )

    # Automatic homologation is a system action. Keeping actor_id nullable is
    # more truthful than attributing it to an administrator who did not click.
    op.drop_constraint(
        op.f("fk_league_audit_events_actor_id_users"),
        "league_audit_events",
        type_="foreignkey",
    )
    op.alter_column("league_audit_events", "actor_id", nullable=True)
    op.create_foreign_key(
        op.f("fk_league_audit_events_actor_id_users"),
        "league_audit_events",
        "users",
        ["actor_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_league_audit_events_actor_id_users"),
        "league_audit_events",
        type_="foreignkey",
    )
    op.execute(
        "DELETE FROM league_audit_events "
        "WHERE actor_id IS NULL AND action::text = 'fantasy_round_homologated'"
    )
    op.alter_column("league_audit_events", "actor_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_league_audit_events_actor_id_users"),
        "league_audit_events",
        "users",
        ["actor_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index(
        "uq_player_match_ratings_league_fixture_athlete_formula",
        table_name="player_match_ratings",
    )
    op.drop_index(
        "uq_player_match_ratings_global_fixture_athlete_formula",
        table_name="player_match_ratings",
    )
    # A downgrade cannot merge two league-specific snapshots losslessly.
    # Preserve historical global rows and remove only the new scoped copies.
    op.execute("DELETE FROM player_match_ratings WHERE league_id IS NOT NULL")
    op.create_unique_constraint(
        "uq_player_match_ratings_fixture_athlete_formula",
        "player_match_ratings",
        ["fixture_id", "athlete_provider_id", "formula_version"],
    )
    op.drop_index(op.f("ix_player_match_ratings_league_id"), table_name="player_match_ratings")
    op.drop_constraint(
        op.f("fk_player_match_ratings_league_id_leagues"),
        "player_match_ratings",
        type_="foreignkey",
    )
    op.drop_column("player_match_ratings", "league_id")
