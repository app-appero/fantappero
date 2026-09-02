"""League-scoped role override persistence helpers (EP04-04)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRole
from sports_data.listone.models import LeagueRoleOverride
from sports_data.listone.validators import is_override_effective, resolve_effective_role


def get_active_override(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
) -> LeagueRoleOverride | None:
    return session.execute(
        select(LeagueRoleOverride).where(
            LeagueRoleOverride.league_id == league_id,
            LeagueRoleOverride.athlete_id == athlete_id,
            LeagueRoleOverride.superseded_at.is_(None),
        )
    ).scalar_one_or_none()


def list_active_overrides(
    session: Session,
    *,
    league_id: UUID,
) -> list[LeagueRoleOverride]:
    return list(
        session.execute(
            select(LeagueRoleOverride).where(
                LeagueRoleOverride.league_id == league_id,
                LeagueRoleOverride.superseded_at.is_(None),
            )
        )
        .scalars()
        .all()
    )


def supersede_override(row: LeagueRoleOverride) -> None:
    row.superseded_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)


def create_override(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
    role: FantasyRole,
    effective_from_round: int | None,
    actor_id: UUID,
    reason: str | None,
) -> LeagueRoleOverride:
    existing = get_active_override(session, league_id=league_id, athlete_id=athlete_id)
    if existing is not None:
        supersede_override(existing)
        session.flush()

    row = LeagueRoleOverride(
        league_id=league_id,
        athlete_id=athlete_id,
        role=role,
        effective_from_round=effective_from_round,
        actor_id=actor_id,
        reason=reason,
    )
    session.add(row)
    session.flush()
    return row


def clear_override(
    session: Session,
    *,
    league_id: UUID,
    athlete_id: UUID,
) -> LeagueRoleOverride | None:
    existing = get_active_override(session, league_id=league_id, athlete_id=athlete_id)
    if existing is None:
        return None
    supersede_override(existing)
    session.flush()
    return existing


def effective_role_for_athlete(
    *,
    official_role: FantasyRole,
    override: LeagueRoleOverride | None,
    current_round: int,
) -> FantasyRole:
    if override is None:
        return official_role
    return resolve_effective_role(
        official_role=official_role,
        override_role=override.role,
        override_effective_from_round=override.effective_from_round,
        current_round=current_round,
    )


def override_is_pending(
    *,
    override: LeagueRoleOverride | None,
    current_round: int,
) -> bool:
    if override is None:
        return False
    return not is_override_effective(
        effective_from_round=override.effective_from_round,
        current_round=current_round,
    )
