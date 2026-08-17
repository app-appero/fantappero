"""Integration tests for round-level H2H scoring and standings (EP07-05 / EP07-06)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import (
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueMemberRole,
    LeagueState,
    LineupSlotKind,
    PlatformRole,
)
from database.session import create_session_factory
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.league import League
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.models.league_standing import LeagueStanding
from leagues.scoring import fantasy_goals_for_points
from leagues.scoring_service import compute_round_results
from leagues.standings_service import compute_league_standings
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import Fixture
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"

# West Ham (home, club 48), modulo 4-5-1: stessa formazione di EP07-04
# (Fornals senza voto, sostituito da Benrahma).
WEST_HAM_STARTERS = [
    (253, "P"),
    (1231, "D"),
    (2726, "D"),
    (21694, "D"),
    (2284, "D"),
    (1243, "C"),
    (2938, "C"),
    (19428, "C"),
    (1646, "C"),
    (1697, "C"),  # Fornals, senza voto
    (18819, "A"),
]
WEST_HAM_BENCH = [(2869, "C"), (19361, "C"), (18817, "D")]

# Chelsea (away, club 49), modulo 3-4-3: undici titolari tutti con voto,
# nessuna sostituzione necessaria.
CHELSEA_STARTERS = [
    (18959, "P"),
    (21998, "D"),
    (259, "D"),
    (152953, "D"),
    (161907, "C"),
    (5996, "C"),
    (67972, "C"),
    (2933, "C"),
    (645, "A"),
    (138935, "A"),
    (283058, "A"),
]
CHELSEA_BENCH = [(63577, "C"), (116117, "C"), (136723, "A")]


@pytest.fixture()
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def _seed_catalog(session: Session) -> None:
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    teams = parse_envelope(_load("reference/teams.json"), endpoint="/teams", http_status=200)
    sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=[TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026)],
    )


def _sync_match(session: Session) -> Fixture:
    fixtures_env = parse_envelope(
        _load("matches/39/1035055/fixtures.json"),
        endpoint="/fixtures",
        http_status=200,
    )
    details = [
        FixtureDetailBatch(
            fixture_provider_id=1035055,
            events_envelope=parse_envelope(
                _load("matches/39/1035055/fixtures_events.json"),
                endpoint="/fixtures/events",
                http_status=200,
            ),
            lineups_envelope=parse_envelope(
                _load("matches/39/1035055/fixtures_lineups.json"),
                endpoint="/fixtures/lineups",
                http_status=200,
            ),
            players_envelope=parse_envelope(
                _load("matches/39/1035055/fixtures_players.json"),
                endpoint="/fixtures/players",
                http_status=200,
            ),
        ),
    ]
    sync_fixtures(session, fixtures_envelopes=[fixtures_env], detail_batches=details)
    return session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()


def _make_user(session: Session) -> User:
    now = datetime.now(UTC)
    user = User(
        email=f"coach-{uuid4()}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=now,
    )
    session.add(user)
    session.flush()
    return user


def _make_lineup(
    session: Session,
    *,
    league_id,
    round_id,
    team_id,
    user_id,
    module: str,
    starters: list[tuple[int, str]],
    bench: list[tuple[int, str]],
    athletes_by_provider_id: dict[int, Athlete],
) -> None:
    now = datetime.now(UTC)
    submission = LineupSubmission(
        league_id=league_id,
        round_id=round_id,
        fantasy_team_id=team_id,
        module=module,
        submitted_at=now,
        submitted_by_user_id=user_id,
    )
    session.add(submission)
    session.flush()
    for order, (provider_id, role) in enumerate(starters):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athletes_by_provider_id[provider_id].id,
                slot_kind=LineupSlotKind.STARTER,
                role=role,
                sort_order=order,
            )
        )
    for order, (provider_id, role) in enumerate(bench):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athletes_by_provider_id[provider_id].id,
                slot_kind=LineupSlotKind.BENCH,
                role=role,
                sort_order=order,
            )
        )


def _build_two_team_round(session: Session, fixture: Fixture) -> tuple[FantasyRound, dict]:
    now = datetime.now(UTC)
    west_ham_user = _make_user(session)
    chelsea_user = _make_user(session)

    league = League(name="Lega Scontro Diretto", season_year=2026, state=LeagueState.ACTIVE)
    session.add(league)
    session.flush()
    session.add(LeagueRules(league_id=league.id))
    session.add(
        LeagueMembership(league_id=league.id, user_id=west_ham_user.id, role=LeagueMemberRole.OWNER)
    )
    session.add(
        LeagueMembership(league_id=league.id, user_id=chelsea_user.id, role=LeagueMemberRole.MEMBER)
    )
    session.flush()
    west_ham_membership = session.scalars(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == west_ham_user.id,
        )
    ).one()
    chelsea_membership = session.scalars(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == chelsea_user.id,
        )
    ).one()

    west_ham_team = FantasyTeam(
        league_id=league.id, membership_id=west_ham_membership.id, name="West Ham Fantasy"
    )
    chelsea_team = FantasyTeam(
        league_id=league.id, membership_id=chelsea_membership.id, name="Chelsea Fantasy"
    )
    session.add(west_ham_team)
    session.add(chelsea_team)
    session.flush()

    fantasy_round = FantasyRound(
        league_id=league.id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now,
        window_end_at=now + timedelta(days=3),
        status=FantasyTurnStatus.LOCKED,
        generated_at=now,
    )
    session.add(fantasy_round)
    session.flush()
    session.add(
        FantasyRoundFixture(round_id=fantasy_round.id, league_id=league.id, fixture_id=fixture.id)
    )

    calendar = LeagueCalendar(
        league_id=league.id,
        algorithm_version="test",
        participant_fingerprint="test",
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
            home_membership_id=west_ham_membership.id,
            away_membership_id=chelsea_membership.id,
        )
    )

    provider_ids = [
        pid for pid, _ in [*WEST_HAM_STARTERS, *WEST_HAM_BENCH, *CHELSEA_STARTERS, *CHELSEA_BENCH]
    ]
    athletes_by_provider_id = {
        row.provider_id: row
        for row in session.scalars(
            select(Athlete).where(Athlete.provider_id.in_(provider_ids))
        ).all()
    }

    _make_lineup(
        session,
        league_id=league.id,
        round_id=fantasy_round.id,
        team_id=west_ham_team.id,
        user_id=west_ham_user.id,
        module="4-5-1",
        starters=WEST_HAM_STARTERS,
        bench=WEST_HAM_BENCH,
        athletes_by_provider_id=athletes_by_provider_id,
    )
    _make_lineup(
        session,
        league_id=league.id,
        round_id=fantasy_round.id,
        team_id=chelsea_team.id,
        user_id=chelsea_user.id,
        module="3-4-3",
        starters=CHELSEA_STARTERS,
        bench=CHELSEA_BENCH,
        athletes_by_provider_id=athletes_by_provider_id,
    )
    session.commit()
    return fantasy_round, {"west_ham": west_ham_team, "chelsea": chelsea_team}


def test_compute_round_results_real_h2h(db_session: Session) -> None:
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()

    result = compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    assert result.matchups == 1
    assert result.counters.created == 1
    assert result.counters.skipped == 0
    assert result.result_final is True  # fixture status_short == "FT"

    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).one()
    slot = db_session.scalars(
        select(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
    ).one()

    assert slot.home_score is not None
    assert slot.away_score is not None
    assert slot.home_fantasy_goals == fantasy_goals_for_points(slot.home_score)
    assert slot.away_fantasy_goals == fantasy_goals_for_points(slot.away_score)
    assert slot.outcome in {"home", "away", "draw"}
    assert slot.result_final is True
    assert slot.result_computed_at is not None

    # Ricalcolo deterministico: nessun cambiamento.
    again = compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()
    assert again.counters.created == 0
    assert again.counters.updated == 0
    assert again.counters.unchanged == 1


def test_compute_round_results_skips_team_without_effective_lineup(db_session: Session) -> None:
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, _teams = _build_two_team_round(db_session, fixture)
    # Nessun EffectiveLineup calcolato: la precondizione FR-SCO-03
    # ("sostituzioni calcolate") non è soddisfatta.
    result = compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    assert result.matchups == 1
    assert result.counters.skipped == 1
    assert result.counters.created == 0


def test_compute_league_standings_after_round_results(db_session: Session) -> None:
    """EP07-06: la classifica riflette il risultato finale dello scontro diretto."""
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()
    compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    result = compute_league_standings(db_session, league_id=fantasy_round.league_id)
    db_session.commit()

    assert result.teams == 2
    assert result.matches_considered == 1
    assert result.counters.created == 2

    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).one()
    slot = db_session.scalars(
        select(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
    ).one()

    standings = {
        row.fantasy_team_id: row
        for row in db_session.scalars(
            select(LeagueStanding).where(LeagueStanding.league_id == fantasy_round.league_id)
        ).all()
    }
    west_ham_standing = standings[teams["west_ham"].id]
    chelsea_standing = standings[teams["chelsea"].id]

    assert west_ham_standing.played == 1
    assert chelsea_standing.played == 1
    assert west_ham_standing.fantasy_goals_for == slot.home_fantasy_goals
    assert west_ham_standing.fantasy_goals_against == slot.away_fantasy_goals
    assert chelsea_standing.fantasy_goals_for == slot.away_fantasy_goals
    assert chelsea_standing.fantasy_goals_against == slot.home_fantasy_goals
    # Le due posizioni sono 1 e 2 in ordine coerente con l'esito.
    assert {west_ham_standing.position, chelsea_standing.position} == {1, 2}
    if slot.outcome == "home":
        assert west_ham_standing.points == 3 and chelsea_standing.points == 0
        assert west_ham_standing.position == 1
    elif slot.outcome == "away":
        assert chelsea_standing.points == 3 and west_ham_standing.points == 0
        assert chelsea_standing.position == 1
    else:
        assert west_ham_standing.points == 1 and chelsea_standing.points == 1

    # Ricalcolo: nessun accumulo, i valori restano identici.
    again = compute_league_standings(db_session, league_id=fantasy_round.league_id)
    db_session.commit()
    assert again.counters.created == 0
    assert again.counters.updated == 0
    assert again.counters.unchanged == 2
    refreshed = db_session.scalars(
        select(LeagueStanding).where(
            LeagueStanding.league_id == fantasy_round.league_id,
            LeagueStanding.fantasy_team_id == teams["west_ham"].id,
        )
    ).one()
    assert refreshed.played == 1
