"""Promote an already-registered user to platform operator (EP11-04a).

Usage (Docker Compose):

    docker compose run --rm api python -m devtools.bootstrap_operator
    docker compose run --rm api python -m devtools.bootstrap_operator --email you@example.com

Reads --email, or falls back to BOOTSTRAP_OPERATOR_EMAIL if omitted. No-op
(exit 0) if an operator already exists — safe to leave configured and re-run
in any environment, including production. Never creates accounts and never
prints credentials or secrets.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from auth.models.user import User
from config.settings.loader import get_api_settings
from database.enums import PlatformRole
from database.session import create_engine_from_url, create_session_factory
from observability.logging import get_logger

_logger = get_logger(__name__)


def bootstrap_operator(session: Session, *, email: str) -> str:
    """Promote the user matching ``email`` to operator; return an outcome message."""
    existing_operator = session.scalar(
        select(func.count(User.id)).where(User.platform_role == PlatformRole.OPERATOR)
    )
    if existing_operator:
        return "An operator already exists; bootstrap is a no-op."

    normalized_email = email.strip().lower()
    user = session.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if user is None:
        msg = "No registered user found for the given email. Register the account first."
        raise ValueError(msg)

    user.platform_role = PlatformRole.OPERATOR
    session.commit()
    _logger.info(
        "admin operator role changed",
        extra={"event": "admin_operator_bootstrapped", "target_user_id": str(user.id)},
    )
    return f"Promoted user {user.id} to operator."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the first platform operator.")
    parser.add_argument(
        "--email",
        default=None,
        help="Email of an already-registered user. Defaults to BOOTSTRAP_OPERATOR_EMAIL.",
    )
    args = parser.parse_args(argv)

    settings = get_api_settings()
    email = args.email or settings.bootstrap_operator_email
    if not email:
        print(
            "Missing --email and BOOTSTRAP_OPERATOR_EMAIL is not set.",
            file=sys.stderr,
        )
        return 2
    if not settings.database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    engine = create_engine_from_url(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            try:
                message = bootstrap_operator(session, email=email)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        print(message)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
