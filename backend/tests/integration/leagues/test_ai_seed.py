"""Development AI-manager seed coverage."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import selectinload

from auth.models.user import User
from database.enums import UserType
from database.session import create_session_factory
from devtools.seed_ai_managers import (
    DEFAULT_COUNT,
    SEED_EMAIL_DOMAIN,
    ai_manager_display_name,
    seed_ai_managers,
)


def test_ai_manager_seed_is_idempotent_verified_and_available(
    migrated_engine: Engine,
) -> None:
    with create_session_factory(migrated_engine)() as session:
        first_created = seed_ai_managers(session, count=DEFAULT_COUNT)
        second_created = seed_ai_managers(session, count=DEFAULT_COUNT)
        rows = session.scalars(
            select(User)
            .where(User.email.like(f"%@{SEED_EMAIL_DOMAIN}"))
            .options(selectinload(User.profile))
            .order_by(User.email)
        ).all()
        seeded_count = session.scalar(
            select(func.count(User.id)).where(
                User.email.like(f"%@{SEED_EMAIL_DOMAIN}"),
                User.user_type == UserType.AI,
            )
        )
        assert first_created == DEFAULT_COUNT
        assert second_created == 0
        assert seeded_count == DEFAULT_COUNT
        assert len(rows) == DEFAULT_COUNT
        for index, row in enumerate(rows, start=1):
            assert row.user_type == UserType.AI
            assert row.email_verified_at is not None
            assert row.profile is not None
            assert row.profile.display_name == ai_manager_display_name(index)
            assert row.profile.available_for_invites is True


def test_seed_main_rejects_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings.base import FantapperoEnv
    from config.settings.loader import get_api_settings
    from devtools import seed_ai_managers as module

    settings = get_api_settings()
    monkeypatch.setattr(settings, "fantappero_env", FantapperoEnv.PRODUCTION)
    monkeypatch.setattr(module, "get_api_settings", lambda: settings)
    assert module.main(["--count", "10"]) == 2
