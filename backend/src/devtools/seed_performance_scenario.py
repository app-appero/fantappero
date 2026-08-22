"""Seed the isolated EP12-03 load-test dataset.

This deliberately derives its domain state from the EP12-01 E2E seeder:
catalog/fixture fixtures, validated rosters, lineups, computed results and
standings all go through the same helpers and services.  It hard-refuses any
database except the dedicated ``postgres-perf/fantappero_performance`` target.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import database.models  # noqa: F401 -- register ORM mappers
from auth.models.user import User
from auth.security import hash_password
from authorization.service import AuthorizationService
from config.settings.base import FantapperoEnv
from config.settings.loader import get_api_settings
from database.enums import FantasyRole, LineupSlotKind, PlatformRole
from database.session import create_engine_from_url, create_session_factory
from devtools.seed_e2e_scenario import (
    POOL_PROVIDER_BASE,
    ROLE_QUOTA,
    _ensure_synthetic_pool,
    _roster_pool_clubs,
    _seed_direct_lineup,
    _sync_catalog_and_fixture,
    stage_results,
    stage_roster,
)
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_teams.factory import find_team_for_membership
from fantasy_teams.models import FantasyRosterSlot
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.schemas import CreateLeagueRequest
from leagues.service import LeagueService
from sports_data.roster.models import Athlete

EXPECTED_DATABASE_HOST = "postgres-perf"
EXPECTED_DATABASE_NAME = "fantappero_performance"
CONFIRMATION_VALUE = "isolated-performance-only"
DEFAULT_PASSWORD = "PerfBeta-Only-2026!"


def _guard_isolated_target(database_url: str | None, environment: FantapperoEnv) -> None:
    if environment is FantapperoEnv.PRODUCTION:
        raise SystemExit("Refusing performance seed in production.")
    if os.getenv("PERFORMANCE_SEED_CONFIRM") != CONFIRMATION_VALUE:
        raise SystemExit(
            f"Set PERFORMANCE_SEED_CONFIRM={CONFIRMATION_VALUE} for the isolated profile."
        )
    if not database_url:
        raise SystemExit("DATABASE_URL is required.")
    parsed = make_url(database_url)
    if parsed.host != EXPECTED_DATABASE_HOST or parsed.database != EXPECTED_DATABASE_NAME:
        raise SystemExit(
            "Refusing unsafe performance target: expected "
            f"host={EXPECTED_DATABASE_HOST}, database={EXPECTED_DATABASE_NAME}; "
            f"received host={parsed.host!r}, database={parsed.database!r}."
        )


def _ensure_user(session: Session, *, index: int, password: str) -> User:
    # EmailStr rejects special-use `.local` addresses at the HTTP login boundary.
    email = f"perf-user-{index:02d}@example.com"
    user = session.scalar(select(User).where(User.email == email))
    password_digest = hash_password(password)
    if user is None:
        user = User(
            email=email,
            password_hash=password_digest,
            email_verified_at=datetime.now(UTC),
            platform_role=PlatformRole.USER,
        )
        session.add(user)
    else:
        user.password_hash = password_digest
        user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    session.commit()
    return user


def _ensure_league(
    session: Session,
    *,
    user: User,
    name: str,
    competition_ids: list,
) -> League:
    league = session.scalar(select(League).where(League.name == name))
    if league is not None:
        return league
    service = LeagueService(session, AuthorizationService(session))
    created = service.create_league(
        user,
        CreateLeagueRequest(
            name=name,
            seasonYear=2026,
            competitionIds=competition_ids,
        ),
    )
    league = session.get(League, created.id)
    assert league is not None
    return league


def _home_pool(session: Session, *, season_year: int) -> dict[FantasyRole, list[Athlete]]:
    # Reuse the EP12-01 helper rather than maintain a second synthetic dataset.
    return _ensure_synthetic_pool(
        session,
        pool="home",
        season_year=season_year,
        clubs=_roster_pool_clubs(session),
    )


def _seed_owner_lineup(session: Session, *, league: League, user: User) -> tuple:
    membership = session.scalar(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == user.id,
        )
    )
    assert membership is not None
    team = find_team_for_membership(session, membership.id)
    assert team is not None
    fantasy_round = session.scalar(
        select(FantasyRound)
        .where(FantasyRound.league_id == league.id)
        .order_by(FantasyRound.number.asc())
        .limit(1)
    )
    assert fantasy_round is not None
    _seed_direct_lineup(
        session,
        league=league,
        round_id=fantasy_round.id,
        team=team,
        owner_id=user.id,
        pool=_home_pool(session, season_year=league.season_year),
    )
    return fantasy_round, team


def _lineup_payload(session: Session, *, round_id, team_id) -> tuple[dict[str, object], int]:
    submission = session.scalar(
        select(LineupSubmission).where(
            LineupSubmission.round_id == round_id,
            LineupSubmission.fantasy_team_id == team_id,
        )
    )
    assert submission is not None
    players = session.scalars(
        select(LineupPlayer)
        .where(LineupPlayer.submission_id == submission.id)
        .order_by(LineupPlayer.slot_kind, LineupPlayer.sort_order)
    ).all()
    starters = [
        str(player.athlete_id) for player in players if player.slot_kind == LineupSlotKind.STARTER
    ]
    roster_ids = list(
        session.scalars(
            select(FantasyRosterSlot.athlete_id)
            .where(
                FantasyRosterSlot.fantasy_team_id == team_id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
            .order_by(FantasyRosterSlot.slot_index.asc())
        )
    )
    starter_set = set(starters)
    # EP12-01's direct opponent lineup needs only four useful substitutes for
    # scoring.  The public save endpoint is stricter and requires every
    # remaining roster athlete, exactly as the real UI sends it.
    bench = [str(athlete_id) for athlete_id in roster_ids if str(athlete_id) not in starter_set]
    first_slot = session.scalar(
        select(FantasyRosterSlot.slot_index)
        .where(
            FantasyRosterSlot.fantasy_team_id == team_id,
            FantasyRosterSlot.athlete_id.is_not(None),
        )
        .order_by(FantasyRosterSlot.slot_index.asc())
        .limit(1)
    )
    assert first_slot is not None
    return (
        {
            "module": submission.module.value,
            "starterAthleteIds": starters,
            "benchAthleteIds": bench,
        },
        first_slot,
    )


def seed(session: Session, *, user_count: int, password: str) -> dict[str, object]:
    _sync_catalog_and_fixture(session)
    # Mirror the EP12-01 UI flow (`create-league-select-all`).  Choosing only
    # the first three would leave the synthetic roster spanning just one of
    # the league's selected competitions and therefore not validated.
    competition_ids = list(
        session.scalars(select(Competition.id).order_by(Competition.provider_id.asc()))
    )
    if len(competition_ids) < 3:
        raise SystemExit("The fixture dataset did not create the required competitions.")

    users: list[dict[str, object]] = []
    for index in range(1, user_count + 1):
        user = _ensure_user(session, index=index, password=password)
        active_name = f"PERF Active {index:02d}"
        history_name = f"PERF History {index:02d}"
        active = _ensure_league(
            session,
            user=user,
            name=active_name,
            competition_ids=competition_ids,
        )
        history = _ensure_league(
            session,
            user=user,
            name=history_name,
            competition_ids=competition_ids,
        )

        stage_roster(session, league_name=active.name, owner_email=user.email, participants=1)
        active_round, active_team = _seed_owner_lineup(session, league=active, user=user)

        stage_roster(session, league_name=history.name, owner_email=user.email, participants=1)
        history_round, _history_team = _seed_owner_lineup(session, league=history, user=user)
        stage_results(session, league_name=history.name, owner_email=user.email)

        lineup, release_slot_index = _lineup_payload(
            session,
            round_id=active_round.id,
            team_id=active_team.id,
        )
        users.append(
            {
                "email": user.email,
                "activeLeagueId": str(active.id),
                "activeRoundId": str(active_round.id),
                "historicalLeagueId": str(history.id),
                "historicalRoundId": str(history_round.id),
                "lineup": lineup,
                "releaseSlotIndex": release_slot_index,
            }
        )

    # Keep synthetic credentials out of versioned evidence; this manifest is
    # written only below artifacts/, which the repository ignores.
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "password": password,
        "users": users,
        "dataset": {
            "source": "EP12-01 devtools.seed_e2e_scenario + API-Football fixtures",
            "homePoolProviderBase": POOL_PROVIDER_BASE["home"],
            "rosterQuota": {role.value: count for role, count in ROLE_QUOTA},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed isolated EP12-03 performance data.")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--output", default="/artifacts/runtime/seed.json")
    args = parser.parse_args(argv)
    if not 1 <= args.users <= 50:
        parser.error("--users must be between 1 and 50")

    settings = get_api_settings()
    _guard_isolated_target(settings.database_url, settings.fantappero_env)
    password = os.getenv("PERF_TEST_PASSWORD", DEFAULT_PASSWORD)
    engine = create_engine_from_url(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            manifest = seed(session, user_count=args.users, password=password)
    finally:
        engine.dispose()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"performance dataset ready; users={len(manifest['users'])} output={output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130) from None
