"""Development AI-manager history seed coverage."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Engine

from auth.models.user import User
from database.session import create_session_factory
from devtools.seed_ai_manager_history import (
    FILLER_EMAIL_DOMAIN,
    HISTORY,
    seed_ai_manager_history,
)
from devtools.seed_ai_managers import ai_manager_email
from leagues.coach_history_service import load_history


def test_history_seed_is_idempotent_and_matches_declared_placements(
    migrated_engine: Engine,
) -> None:
    with create_session_factory(migrated_engine)() as session:
        first = seed_ai_manager_history(session)
        second = seed_ai_manager_history(session)

        assert first["avatars_updated"] > 0
        assert first["leagues_created"] == sum(len(items) for items in HISTORY.values())
        assert second == {"avatars_updated": 0, "leagues_created": 0}

        for index, placements in HISTORY.items():
            coach = session.scalar(select(User).where(User.email == ai_manager_email(index)))
            assert coach is not None
            history = load_history(session, user_id=coach.id)
            assert history.concluded_leagues == len(placements)
            expected_best = min(position for _, position, *_ in placements)
            assert history.best_position == expected_best


def test_filler_participants_stay_unverified(migrated_engine: Engine) -> None:
    with create_session_factory(migrated_engine)() as db_session:
        seed_ai_manager_history(db_session)
        fillers = db_session.scalars(
            select(User).where(User.email.like(f"%@{FILLER_EMAIL_DOMAIN}"))
        ).all()
        assert fillers
        assert all(user.email_verified_at is None for user in fillers)
