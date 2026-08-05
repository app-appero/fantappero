"""Idempotent seed of AI fantasy coaches for local development.

Usage (Docker Compose):

    docker compose run --rm api python -m devtools.seed_ai_managers --count 10

Refuses to run in production. Never prints credentials or secrets.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers (LeagueMembership, …)
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.security import hash_password
from config.settings.base import FantapperoEnv
from config.settings.loader import get_api_settings
from database.enums import PlatformRole, UserType
from database.session import create_engine_from_url, create_session_factory

SEED_EMAIL_DOMAIN = "ai-managers.example.com"
DEFAULT_COUNT = 10


def ai_manager_email(index: int) -> str:
    return f"allenatore-ia-{index:02d}@{SEED_EMAIL_DOMAIN}"


def ai_manager_display_name(index: int) -> str:
    return f"Allenatore IA {index:02d}"


def seed_ai_managers(session: Session, *, count: int = DEFAULT_COUNT) -> int:
    """Upsert exactly ``count`` deterministic AI managers; return newly created rows."""
    if count < 1:
        msg = "--count must be >= 1"
        raise ValueError(msg)

    created = 0
    verified_at = datetime.now(UTC)
    for index in range(1, count + 1):
        email = ai_manager_email(index)
        display_name = ai_manager_display_name(index)
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            # Unusable credential: random secret, never logged or returned.
            user = User(
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(48)),
                platform_role=PlatformRole.USER,
                user_type=UserType.AI,
                email_verified_at=verified_at,
            )
            session.add(user)
            session.flush()
            created += 1
        else:
            if user.user_type != UserType.AI:
                msg = f"Refusing to convert existing non-AI account for seed index {index:02d}"
                raise RuntimeError(msg)
            user.user_type = UserType.AI
            if user.email_verified_at is None:
                user.email_verified_at = verified_at
            user.deleted_at = None

        profile = session.get(UserProfile, user.id)
        if profile is None:
            profile = UserProfile(user_id=user.id)
            session.add(profile)
        profile.display_name = display_name
        profile.available_for_invites = True

    session.commit()
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed local AI fantasy coaches.")
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of AI managers to upsert (default: {DEFAULT_COUNT})",
    )
    args = parser.parse_args(argv)

    settings = get_api_settings()
    if settings.fantappero_env is FantapperoEnv.PRODUCTION:
        print("Refusing to seed AI managers in production.", file=sys.stderr)
        return 2
    if settings.fantappero_env not in {FantapperoEnv.DEVELOPMENT, FantapperoEnv.TEST}:
        print(
            "AI manager seed is allowed only in development or test environments.",
            file=sys.stderr,
        )
        return 2
    if not settings.database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    engine = create_engine_from_url(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            created = seed_ai_managers(session, count=args.count)
        print(f"AI fantasy coaches ready; count={args.count}; created={created}")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
