"""Idempotent seed of avatars + concluded-league history for AI managers.

Extends ``devtools.seed_ai_managers``: gives the seeded AI coaches a photo
and a realistic storico (EP13-P06) so the coach directory/profile UI can be
reviewed against real API data instead of frontend demo fixtures.

Usage (Docker Compose):

    docker compose exec api python -m devtools.seed_ai_manager_history

Refuses to run in production. Never prints credentials or secrets.
"""

from __future__ import annotations

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
from database.enums import LeagueMemberRole, LeagueState, PlatformRole, UserType
from database.session import create_engine_from_url, create_session_factory
from devtools.seed_ai_managers import (
    DEFAULT_COUNT,
    ai_manager_email,
    seed_ai_managers,
)
from fantasy_teams.models import FantasyTeam
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_standing import LeagueStanding

FILLER_EMAIL_DOMAIN = "ai-history-filler.example.com"
MAX_FILLERS = 9

#: (index, avatar) — avatar is None to keep one manager on the initial-letter fallback.
AVATARS = {index: index != 4 for index in range(1, DEFAULT_COUNT + 1)}

#: index -> placements, each
#: (season_year, position, participants, played, won, drawn, lost, points, fantasy_points_for)
HISTORY: dict[int, list[tuple[int, int, int, int, int, int, int, int, float]]] = {
    1: [(2025, 4, 8, 14, 7, 3, 4, 24, 690.0)],
    2: [
        (2026, 2, 6, 10, 6, 2, 2, 20, 720.0),
        (2025, 6, 8, 14, 3, 3, 8, 12, 580.0),
    ],
    3: [(2026, 5, 8, 14, 5, 3, 6, 18, 655.0)],
    4: [
        (2026, 2, 6, 10, 6, 1, 3, 19, 710.0),
        (2025, 7, 8, 14, 2, 2, 10, 8, 520.0),
    ],
    5: [(2025, 1, 6, 10, 8, 1, 1, 25, 790.0)],
    6: [
        (2026, 3, 8, 14, 6, 3, 5, 21, 660.0),
        (2025, 1, 6, 10, 7, 2, 1, 23, 750.0),
        (2024, 8, 10, 18, 2, 2, 14, 8, 480.0),
    ],
    7: [
        (2026, 1, 10, 18, 13, 3, 2, 42, 905.0),
        (2025, 2, 10, 18, 11, 4, 3, 37, 870.0),
        (2024, 5, 8, 14, 6, 3, 5, 21, 650.0),
        (2023, 3, 6, 10, 6, 2, 2, 20, 605.0),
    ],
    8: [(2026, 6, 10, 18, 5, 4, 9, 19, 610.0)],
    9: [(2026, 3, 8, 14, 7, 2, 5, 23, 700.0)],
    10: [
        (2026, 1, 8, 14, 10, 2, 2, 32, 830.0),
        (2025, 4, 6, 10, 4, 2, 4, 14, 590.0),
    ],
}


def _avatar_url(index: int) -> str | None:
    if not AVATARS.get(index, True):
        return None
    return f"https://i.pravatar.cc/150?u={ai_manager_email(index)}"


def _filler_email(index: int) -> str:
    return f"seed-filler-{index:02d}@{FILLER_EMAIL_DOMAIN}"


def _get_or_create_filler(session: Session, index: int) -> User:
    email = _filler_email(index)
    user = session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    # Unverified on purpose: filler participants must never show up in any
    # coach directory (the directory query requires email_verified_at).
    user = User(
        email=email,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        platform_role=PlatformRole.USER,
        user_type=UserType.HUMAN,
        email_verified_at=None,
    )
    session.add(user)
    session.flush()
    return user


def _league_exists(session: Session, name: str) -> bool:
    return session.scalar(select(League.id).where(League.name == name)) is not None


def _seed_placement(
    session: Session,
    *,
    coach: User,
    manager_index: int,
    season_year: int,
    position: int,
    participants: int,
    played: int,
    won: int,
    drawn: int,
    lost: int,
    points: int,
    fantasy_points_for: float,
) -> bool:
    if participants < 1 or participants - 1 > MAX_FILLERS:
        msg = f"participants must be between 1 and {MAX_FILLERS + 1}"
        raise ValueError(msg)

    name = f"Seed storico IA {manager_index:02d} — S{season_year}"
    if _league_exists(session, name):
        return False

    league = League(name=name, season_year=season_year, state=LeagueState.CONCLUDED)
    session.add(league)
    session.flush()

    # 1..participants, each used exactly once; the coach keeps its own position.
    filler_positions = [p for p in range(1, participants + 1) if p != position]

    computed_at = datetime.now(UTC)
    for slot in range(participants):
        if slot == 0:
            member_user = coach
            slot_position = position
            slot_fantasy_points = fantasy_points_for
        else:
            member_user = _get_or_create_filler(session, slot)
            slot_position = filler_positions[slot - 1]
            slot_fantasy_points = 0.0

        membership = LeagueMembership(
            league_id=league.id,
            user_id=member_user.id,
            role=LeagueMemberRole.OWNER if slot == 0 else LeagueMemberRole.MEMBER,
        )
        session.add(membership)
        session.flush()

        team = FantasyTeam(league_id=league.id, membership_id=membership.id, name=f"Team {slot}")
        session.add(team)
        session.flush()

        session.add(
            LeagueStanding(
                league_id=league.id,
                fantasy_team_id=team.id,
                played=played,
                won=won if slot == 0 else 0,
                drawn=drawn if slot == 0 else 0,
                lost=(lost if slot == 0 else played),
                fantasy_goals_for=0,
                fantasy_goals_against=0,
                fantasy_points_for=slot_fantasy_points,
                points=points if slot == 0 else 0,
                position=slot_position,
                computed_at=computed_at,
            )
        )
    return True


def seed_ai_manager_history(session: Session, *, count: int = DEFAULT_COUNT) -> dict[str, int]:
    """Idempotently give the seeded AI managers a photo and a storico."""
    seed_ai_managers(session, count=count)

    updated_avatars = 0
    for index in range(1, count + 1):
        user = session.scalar(select(User).where(User.email == ai_manager_email(index)))
        if user is None:
            continue
        profile = session.get(UserProfile, user.id)
        if profile is None:
            continue
        avatar_url = _avatar_url(index)
        if profile.avatar_url != avatar_url:
            profile.avatar_url = avatar_url
            updated_avatars += 1

    created_leagues = 0
    for index, placements in HISTORY.items():
        if index > count:
            continue
        coach = session.scalar(select(User).where(User.email == ai_manager_email(index)))
        if coach is None:
            continue
        for (
            season_year,
            position,
            participants,
            played,
            won,
            drawn,
            lost,
            points,
            fantasy_points_for,
        ) in placements:
            created = _seed_placement(
                session,
                coach=coach,
                manager_index=index,
                season_year=season_year,
                position=position,
                participants=participants,
                played=played,
                won=won,
                drawn=drawn,
                lost=lost,
                points=points,
                fantasy_points_for=fantasy_points_for,
            )
            if created:
                created_leagues += 1

    session.commit()
    return {"avatars_updated": updated_avatars, "leagues_created": created_leagues}


def main(argv: list[str] | None = None) -> int:
    del argv
    settings = get_api_settings()
    if settings.fantappero_env is FantapperoEnv.PRODUCTION:
        print("Refusing to seed AI manager history in production.", file=sys.stderr)
        return 2
    if settings.fantappero_env not in {FantapperoEnv.DEVELOPMENT, FantapperoEnv.TEST}:
        print(
            "AI manager history seed is allowed only in development or test environments.",
            file=sys.stderr,
        )
        return 2
    if not settings.database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    engine = create_engine_from_url(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            result = seed_ai_manager_history(session)
        print(
            "AI manager history ready; "
            f"avatars_updated={result['avatars_updated']}; "
            f"leagues_created={result['leagues_created']}"
        )
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
