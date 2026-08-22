"""Seed a full E2E scenario for an existing league (EP12-01).

The Playwright critical-flow suite (``apps/e2e``) drives registration, login
and league creation through the real UI, then calls this script to reach two
states that are not reachable from the UI at all:

* a fully validated roster for every participant (the real path is a sealed
  auction, deliberately out of scope for browser automation — see
  ``docs/operations/beta_readiness/ep12-01_suite_e2e.md``);
* a computed/homologated round result (requires ``Permission.GLOBAL_OPERATE``
  and the "Risultati" tab is a static placeholder today).

Both stages call the real domain services directly (``assign_winning_bid``,
``compute_fixture_ratings``, ``compute_round_results``, ``homologate_round``,
...) — never HTTP, never the UI — reusing the exact fixture-based pipeline
already validated by
``backend/tests/integration/leagues/test_scoring_service.py``.

Usage (Docker Compose):

    docker compose run --rm api python -m devtools.seed_e2e_scenario \\
        --league-name "Lega E2E 123" --owner-email e2e.foo@example.com --stage roster

    docker compose run --rm api python -m devtools.seed_e2e_scenario \\
        --league-name "Lega E2E 123" --owner-email e2e.foo@example.com --stage results

Refuses to run in production. Never prints credentials or secrets. Every
stage is idempotent: running it twice against the same league is a no-op for
whatever it already completed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from config.settings.base import FantapperoEnv
from config.settings.loader import get_api_settings
from database.enums import (
    FantasyRole,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueMemberRole,
    LineupSlotKind,
    PlatformRole,
    RosterCompositionStatus,
)
from database.session import create_engine_from_url, create_session_factory
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_teams.factory import ensure_team_for_membership, find_team_for_membership
from fantasy_teams.models import FantasyTeam
from fantasy_turns.homologation_service import homologate_round
from leagues.models.league import League
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.scoring_service import compute_round_results
from leagues.standings_service import compute_league_standings
from market.assignment import assign_winning_bid
from sports_data.catalog.models import Club
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import Fixture
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.listone.models import RoleAssignment
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete


def _resolve_dataset_dir() -> Path:
    """Locate ``tests/fixtures/api_football`` regardless of how the package
    is installed. In the Docker image the backend is pip-installed
    (non-editable) into site-packages, so ``__file__`` no longer sits next to
    the source tree's ``backend/tests`` — but the Dockerfile also COPYs
    ``backend/tests`` to ``/app/tests``, and the container's WORKDIR is
    ``/app``, so the cwd-relative candidate below is the one that resolves in
    practice. The parents-based candidate keeps this working for a local
    editable install (e.g. ``pip install -e .`` run from ``backend/``).
    """
    candidates = [
        Path.cwd() / "tests" / "fixtures" / "api_football",
        Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "api_football",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    msg = f"Dataset fixture non trovato (candidati: {[str(c) for c in candidates]})."
    raise SystemExit(msg)


DATASET = _resolve_dataset_dir()
FIXTURE_PROVIDER_ID = 1035055
COMPETITION_PROVIDER_ID = 39  # Premier League — same match reused by test_scoring_service.
# Reused to give roster athletes real club/competition links across >=3
# competitions (FR-ROS-02) without depending on the West Ham/Chelsea clubs
# that carry the round's real fixture (avoids spuriously locking them).
EXTRA_COMPETITION_PROVIDER_IDS = (39, 140, 135)
EXCLUDED_CLUB_PROVIDER_IDS = frozenset({48, 49})  # West Ham, Chelsea

# Fixed synthetic athlete pools reused across every seeded league (idempotent,
# no unbounded growth across repeated E2E/CI runs). Roster ownership is
# scoped per-league (`RosterOwnershipInterval.league_id`), so the same
# athlete rows can sit on unrelated teams in different leagues at once.
POOL_PROVIDER_BASE = {"home": 9_100_000, "away": 9_200_000}
ROLE_QUOTA: list[tuple[FantasyRole, int]] = [
    (FantasyRole.P, 3),
    (FantasyRole.D, 11),
    (FantasyRole.C, 11),
    (FantasyRole.A, 10),
]
MAPPING_VERSION = "e2e-seed-v1"


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def _find_league(session: Session, league_name: str) -> League:
    league = session.scalar(select(League).where(League.name == league_name))
    if league is None:
        msg = f"Lega '{league_name}' non trovata. Deve esistere già (creata dal test E2E)."
        raise SystemExit(msg)
    return league


def _find_owner(session: Session, league: League, owner_email: str) -> User:
    owner = session.scalar(select(User).where(User.email == owner_email))
    if owner is None:
        msg = f"Utente owner '{owner_email}' non trovato."
        raise SystemExit(msg)
    membership = session.scalar(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == owner.id,
        )
    )
    if membership is None:
        msg = f"'{owner_email}' non è partecipante della lega '{league.name}'."
        raise SystemExit(msg)
    return owner


def _sync_catalog_and_fixture(session: Session) -> Fixture:
    """Idempotent: sync_catalog/sync_fixtures upsert by provider_id."""
    leagues_env = parse_envelope(
        _load("reference/leagues.json"), endpoint="/leagues", http_status=200
    )
    teams_env = parse_envelope(_load("reference/teams.json"), endpoint="/teams", http_status=200)
    sync_catalog(
        session,
        leagues_envelope=leagues_env,
        teams_batches=[
            TeamsBatch(envelope=teams_env, competition_provider_id=cid, season_year=2026)
            for cid in EXTRA_COMPETITION_PROVIDER_IDS
        ],
    )
    session.commit()

    fixtures_env = parse_envelope(
        _load(f"matches/{COMPETITION_PROVIDER_ID}/{FIXTURE_PROVIDER_ID}/fixtures.json"),
        endpoint="/fixtures",
        http_status=200,
    )
    details = [
        FixtureDetailBatch(
            fixture_provider_id=FIXTURE_PROVIDER_ID,
            events_envelope=parse_envelope(
                _load(
                    f"matches/{COMPETITION_PROVIDER_ID}/{FIXTURE_PROVIDER_ID}/fixtures_events.json"
                ),
                endpoint="/fixtures/events",
                http_status=200,
            ),
            lineups_envelope=parse_envelope(
                _load(
                    f"matches/{COMPETITION_PROVIDER_ID}/{FIXTURE_PROVIDER_ID}/fixtures_lineups.json"
                ),
                endpoint="/fixtures/lineups",
                http_status=200,
            ),
            players_envelope=parse_envelope(
                _load(
                    f"matches/{COMPETITION_PROVIDER_ID}/{FIXTURE_PROVIDER_ID}/fixtures_players.json"
                ),
                endpoint="/fixtures/players",
                http_status=200,
            ),
        ),
    ]
    sync_fixtures(session, fixtures_envelopes=[fixtures_env], detail_batches=details)
    session.commit()
    return session.execute(
        select(Fixture).where(Fixture.provider_id == FIXTURE_PROVIDER_ID)
    ).scalar_one()


def _roster_pool_clubs(session: Session) -> list[Club]:
    clubs = list(
        session.scalars(
            select(Club)
            .where(Club.provider_id.not_in(EXCLUDED_CLUB_PROVIDER_IDS))
            .order_by(Club.provider_id.asc())
        ).all()
    )
    if not clubs:
        msg = "Nessun club sincronizzato per popolare le rose sintetiche."
        raise SystemExit(msg)
    return clubs


def _ensure_synthetic_pool(
    session: Session, *, pool: str, season_year: int, clubs: list[Club]
) -> dict[FantasyRole, list[Athlete]]:
    """Idempotently ensure a fixed 35-athlete pool (3P/11D/11C/10A) exists."""
    base = POOL_PROVIDER_BASE[pool]
    grouped: dict[FantasyRole, list[Athlete]] = {role: [] for role, _ in ROLE_QUOTA}
    provider_id = base
    club_index = 0
    for role, count in ROLE_QUOTA:
        for _ in range(count):
            athlete = session.scalar(select(Athlete).where(Athlete.provider_id == provider_id))
            if athlete is None:
                athlete = Athlete(
                    provider_id=provider_id,
                    canonical_name=f"E2E {pool} {role.value}{provider_id - base}",
                )
                session.add(athlete)
                session.flush()
            assignment = session.scalar(
                select(RoleAssignment).where(
                    RoleAssignment.athlete_id == athlete.id,
                    RoleAssignment.season_year == season_year,
                )
            )
            club = clubs[club_index % len(clubs)]
            club_index += 1
            if assignment is None:
                session.add(
                    RoleAssignment(
                        athlete_id=athlete.id,
                        season_year=season_year,
                        role=role,
                        mapping_version=MAPPING_VERSION,
                        provider_position_raw=role.value,
                        club_id=club.id,
                    )
                )
                session.flush()
            grouped[role].append(athlete)
            provider_id += 1
    session.commit()
    return grouped


def _fill_roster_via_assignment(
    session: Session,
    *,
    league: League,
    team: FantasyTeam,
    pool: dict[FantasyRole, list[Athlete]],
    owner_id: UUID,
) -> None:
    if team.composition_status == RosterCompositionStatus.VALIDATED:
        return
    ordered = [
        *pool[FantasyRole.P],
        *pool[FantasyRole.D],
        *pool[FantasyRole.C],
        *pool[FantasyRole.A],
    ]
    for index, athlete in enumerate(ordered):
        result = assign_winning_bid(
            session,
            league=league,
            team=team,
            athlete_id=athlete.id,
            amount_credits=1,
            transaction_id=f"e2e-seed:{team.id}:{index}",
            actor_id=owner_id,
        )
        if result is None:
            msg = (
                f"Assegnazione rifiutata per team {team.id}, slot #{index} "
                f"(atleta {athlete.id}): credito insufficiente o quota ruolo superata."
            )
            raise SystemExit(msg)
    session.commit()


def _find_or_create_participant(
    session: Session, league: League, *, index: int
) -> LeagueMembership:
    email = f"e2e-seed-participant-{index:02d}@e2e.fantappero.local"
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        import secrets

        from auth.security import hash_password

        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            platform_role=PlatformRole.USER,
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
    membership = session.scalar(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == user.id,
        )
    )
    if membership is None:
        membership = LeagueMembership(
            league_id=league.id,
            user_id=user.id,
            role=LeagueMemberRole.MEMBER,
        )
        session.add(membership)
        session.flush()
    session.commit()
    return membership


def _ensure_round_and_calendar(
    session: Session,
    *,
    league: League,
    fixture: Fixture,
    home_membership: LeagueMembership,
    away_membership: LeagueMembership,
) -> tuple:
    from fantasy_turns.models import FantasyRound, FantasyRoundFixture

    existing = session.scalar(
        select(FantasyRound)
        .where(FantasyRound.league_id == league.id)
        .order_by(FantasyRound.number.asc())
        .limit(1)
    )
    if existing is not None:
        return existing, False

    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=league.id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now,
        window_end_at=now + timedelta(days=3),
        cutoff_at=now + timedelta(days=7),
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
    )
    session.add(fantasy_round)
    session.flush()
    session.add(
        FantasyRoundFixture(round_id=fantasy_round.id, league_id=league.id, fixture_id=fixture.id)
    )

    calendar = session.scalar(select(LeagueCalendar).where(LeagueCalendar.league_id == league.id))
    if calendar is None:
        calendar = LeagueCalendar(
            league_id=league.id,
            algorithm_version="e2e-seed",
            participant_fingerprint="e2e-seed",
            # ck_league_calendars_participants requires 4..10 even though only
            # 2 teams actually play the seeded matchup slot.
            participant_count=4,
            round_count=1,
            matchup_count=1,
            bye_count=0,
            generated_at=now,
        )
        session.add(calendar)
        session.flush()
    session.add(
        LeagueCalendarSlot(
            calendar_id=calendar.id,
            round_number=1,
            slot_index=0,
            is_bye=False,
            home_membership_id=home_membership.id,
            away_membership_id=away_membership.id,
        )
    )
    session.commit()
    return fantasy_round, True


def _seed_direct_lineup(
    session: Session,
    *,
    league: League,
    round_id: UUID,
    team: FantasyTeam,
    owner_id: UUID,
    pool: dict[FantasyRole, list[Athlete]],
) -> None:
    """Bypass UI for the *opponent* team only — the test user's own lineup is
    saved for real through Playwright (FormationPage)."""
    existing = session.scalar(
        select(LineupSubmission).where(
            LineupSubmission.round_id == round_id,
            LineupSubmission.fantasy_team_id == team.id,
        )
    )
    if existing is not None:
        return

    starters = [
        *pool[FantasyRole.P][:1],
        *pool[FantasyRole.D][:4],
        *pool[FantasyRole.C][:3],
        *pool[FantasyRole.A][:3],
    ]
    bench = [
        pool[FantasyRole.P][1],
        pool[FantasyRole.D][4],
        pool[FantasyRole.C][3],
        pool[FantasyRole.A][3],
    ]

    from database.enums import FantasyModule

    submission = LineupSubmission(
        league_id=league.id,
        round_id=round_id,
        fantasy_team_id=team.id,
        module=FantasyModule.M433,
        submitted_at=datetime.now(UTC),
        submitted_by_user_id=owner_id,
    )
    session.add(submission)
    session.flush()
    role_by_athlete = {athlete.id: role for role, athletes in pool.items() for athlete in athletes}
    for order, athlete in enumerate(starters):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athlete.id,
                slot_kind=LineupSlotKind.STARTER,
                role=role_by_athlete[athlete.id],
                sort_order=order,
            )
        )
    for order, athlete in enumerate(bench):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athlete.id,
                slot_kind=LineupSlotKind.BENCH,
                role=role_by_athlete[athlete.id],
                sort_order=order,
            )
        )
    session.commit()


def stage_roster(
    session: Session, *, league_name: str, owner_email: str, participants: int
) -> None:
    league = _find_league(session, league_name)
    owner = _find_owner(session, league, owner_email)

    fixture = _sync_catalog_and_fixture(session)
    clubs = _roster_pool_clubs(session)
    home_pool = _ensure_synthetic_pool(
        session, pool="home", season_year=league.season_year, clubs=clubs
    )
    away_pool = _ensure_synthetic_pool(
        session, pool="away", season_year=league.season_year, clubs=clubs
    )

    owner_membership = session.scalar(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == owner.id,
        )
    )
    assert owner_membership is not None
    owner_team, _ = ensure_team_for_membership(
        session, owner_membership, name=owner.display_name or "Squadra E2E", actor_id=owner.id
    )
    session.commit()

    away_membership = _find_or_create_participant(session, league, index=1)
    for index in range(2, participants + 1):
        _find_or_create_participant(session, league, index=index)
    away_team, _ = ensure_team_for_membership(
        session, away_membership, name="Avversario E2E", actor_id=owner.id
    )
    session.commit()

    owner_team = find_team_for_membership(session, owner_membership.id)
    away_team = find_team_for_membership(session, away_membership.id)
    assert owner_team is not None
    assert away_team is not None

    _fill_roster_via_assignment(
        session, league=league, team=owner_team, pool=home_pool, owner_id=owner.id
    )
    _fill_roster_via_assignment(
        session, league=league, team=away_team, pool=away_pool, owner_id=owner.id
    )

    fantasy_round, _created = _ensure_round_and_calendar(
        session,
        league=league,
        fixture=fixture,
        home_membership=owner_membership,
        away_membership=away_membership,
    )
    _seed_direct_lineup(
        session,
        league=league,
        round_id=fantasy_round.id,
        team=away_team,
        owner_id=owner.id,
        pool=away_pool,
    )

    owner_team = find_team_for_membership(session, owner_membership.id)
    away_team = find_team_for_membership(session, away_membership.id)
    print(
        "roster ready; "
        f"league={league.id} round={fantasy_round.id} "
        f"owner_team_status={owner_team.composition_status.value} "
        f"away_team_status={away_team.composition_status.value}"
    )


def stage_results(session: Session, *, league_name: str, owner_email: str) -> None:
    from fantasy_turns.models import FantasyRound

    league = _find_league(session, league_name)
    owner = _find_owner(session, league, owner_email)

    fantasy_round = session.scalar(
        select(FantasyRound)
        .where(FantasyRound.league_id == league.id)
        .order_by(FantasyRound.number.asc())
        .limit(1)
    )
    if fantasy_round is None:
        msg = "Nessun turno trovato: esegui prima --stage roster."
        raise SystemExit(msg)

    if fantasy_round.homologation_status.value == "homologated":
        print(f"results already homologated; round={fantasy_round.id}")
        return

    fixture_id = session.scalar(
        select(Fixture.id).where(Fixture.provider_id == FIXTURE_PROVIDER_ID)
    )
    assert fixture_id is not None
    try:
        compute_fixture_ratings(session, fixture_id=fixture_id)
        session.commit()
    except ValidationAuthError as exc:
        if exc.code != "round_homologated":
            raise
        # The shared fixture was already rated/homologated by a previous E2E
        # run against a different league — PlayerMatchRating rows persist
        # globally per fixture, so recomputation is unnecessary, not an error.
        session.rollback()

    compute_round_effective_lineups(session, round_id=fantasy_round.id)
    session.commit()

    result = compute_round_results(session, round_id=fantasy_round.id)
    session.commit()

    compute_league_standings(session, league_id=league.id)
    session.commit()

    homologation = homologate_round(session, round_id=fantasy_round.id, actor_id=owner.id)
    session.commit()

    print(
        "results ready; "
        f"league={league.id} round={fantasy_round.id} "
        f"matchups={result.matchups} result_final={result.result_final} "
        f"homologation_status={homologation.homologation_status}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed an E2E critical-flow scenario.")
    parser.add_argument("--league-name", required=True)
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--stage", required=True, choices=["roster", "results"])
    parser.add_argument(
        "--participants",
        type=int,
        default=1,
        help="Additional participants beyond the owner (default: 1, minimum for a H2H round).",
    )
    args = parser.parse_args(argv)

    settings = get_api_settings()
    if settings.fantappero_env is FantapperoEnv.PRODUCTION:
        print("Refusing to seed the E2E scenario in production.", file=sys.stderr)
        return 2
    if settings.fantappero_env not in {FantapperoEnv.DEVELOPMENT, FantapperoEnv.TEST}:
        print(
            "E2E scenario seed is allowed only in development or test environments.",
            file=sys.stderr,
        )
        return 2
    if not settings.database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    engine = create_engine_from_url(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            if args.stage == "roster":
                stage_roster(
                    session,
                    league_name=args.league_name,
                    owner_email=args.owner_email,
                    participants=max(1, args.participants),
                )
            else:
                stage_results(session, league_name=args.league_name, owner_email=args.owner_email)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
