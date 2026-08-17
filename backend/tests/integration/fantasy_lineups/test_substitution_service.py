"""Integration tests for round-level effective lineups (EP07-04 / FR-SUB-01)."""

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
from fantasy_lineups.models import EffectiveLineup, LineupPlayer, LineupSubmission
from fantasy_lineups.substitution_service import (
    compute_round_effective_lineups,
    get_effective_lineup,
)
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import Fixture
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
MATCH = DATASET / "matches" / "39" / "1035055"

# Real West Ham (club provider_id 48) lineup from the offline corpus.
WEST_HAM_STARTERS = [
    (253, "P"),  # Areola
    (1231, "D"),  # Coufal
    (2726, "D"),  # Zouma
    (21694, "D"),  # Aguerd, eligible (67')
    (2284, "D"),  # Emerson
    (1243, "C"),  # Soucek
    (2938, "C"),  # Ward-Prowse
    (19428, "C"),  # Bowen
    (1646, "C"),  # Paqueta
    (1697, "C"),  # Fornals -- SENZA VOTO (14', no relevant event)
    (18819, "A"),  # Antonio
]
# Bench order matters: Alvarez first (ineligible, 9'), then Benrahma (eligible, 69'),
# then Ogbonna (eligible D, 21', no compatible starter to replace).
WEST_HAM_BENCH = [
    (2869, "C"),  # Alvarez -- ineligible (9', no relevant event)
    (19361, "C"),  # Benrahma -- eligible, replaces Fornals
    (18817, "D"),  # Ogbonna -- eligible but no D starter is senza voto
]


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


def _build_league_round_and_lineup(
    session: Session, fixture: Fixture
) -> tuple[FantasyRound, FantasyTeam]:
    now = datetime.now(UTC)
    user = User(
        email=f"coach-{uuid4()}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=now,
    )
    session.add(user)
    session.flush()

    league = League(name="Lega Sostituzioni Reali", season_year=2026, state=LeagueState.ACTIVE)
    session.add(league)
    session.flush()
    session.add(LeagueRules(league_id=league.id))
    session.add(LeagueMembership(league_id=league.id, user_id=user.id, role=LeagueMemberRole.OWNER))
    team = FantasyTeam(league_id=league.id, membership_id=None, name="Squadra Reale")
    session.flush()
    membership = session.scalars(
        select(LeagueMembership).where(LeagueMembership.league_id == league.id)
    ).one()
    team.membership_id = membership.id
    session.add(team)
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

    athletes_by_provider_id = {
        row.provider_id: row
        for row in session.scalars(
            select(Athlete).where(
                Athlete.provider_id.in_([pid for pid, _ in [*WEST_HAM_STARTERS, *WEST_HAM_BENCH]])
            )
        ).all()
    }

    submission = LineupSubmission(
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=team.id,
        module="4-5-1",
        submitted_at=now,
        submitted_by_user_id=user.id,
    )
    session.add(submission)
    session.flush()

    for order, (provider_id, role) in enumerate(WEST_HAM_STARTERS):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athletes_by_provider_id[provider_id].id,
                slot_kind=LineupSlotKind.STARTER,
                role=role,
                sort_order=order,
            )
        )
    for order, (provider_id, role) in enumerate(WEST_HAM_BENCH):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athletes_by_provider_id[provider_id].id,
                slot_kind=LineupSlotKind.BENCH,
                role=role,
                sort_order=order,
            )
        )
    session.commit()
    return fantasy_round, team


def test_compute_round_effective_lineups_real_corpus(db_session: Session) -> None:
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, team = _build_league_round_and_lineup(db_session, fixture)

    result = compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()

    assert result.teams == 1
    assert result.counters.created == 1
    assert result.max_automatic_substitutions == 5

    row = get_effective_lineup(db_session, round_id=fantasy_round.id, fantasy_team_id=team.id)
    assert row is not None
    assert row.module_valid is True
    assert row.max_automatic_substitutions == 5
    assert len(row.substitutions_json) == 1

    fornals = db_session.scalars(select(Athlete).where(Athlete.provider_id == 1697)).one()
    benrahma = db_session.scalars(select(Athlete).where(Athlete.provider_id == 19361)).one()
    alvarez = db_session.scalars(select(Athlete).where(Athlete.provider_id == 2869)).one()
    ogbonna = db_session.scalars(select(Athlete).where(Athlete.provider_id == 18817)).one()

    substitution = row.substitutions_json[0]
    assert substitution["outAthleteId"] == str(fornals.id)
    assert substitution["inAthleteId"] == str(benrahma.id)
    assert substitution["role"] == "C"
    assert substitution["order"] == 1

    assert str(fornals.id) not in row.effective_starter_ids
    assert str(benrahma.id) in row.effective_starter_ids

    skipped_reasons = {item["athleteId"]: item["reason"] for item in row.skipped_json}
    assert skipped_reasons[str(alvarez.id)] == "not_eligible"
    assert skipped_reasons[str(ogbonna.id)] == "no_compatible_starter"

    # Ricalcolo deterministico: nessuna riga duplicata, nessun cambiamento.
    again = compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()
    assert again.counters.created == 0
    assert again.counters.updated == 0
    assert again.counters.unchanged == 1
    rows = db_session.scalars(
        select(EffectiveLineup).where(EffectiveLineup.round_id == fantasy_round.id)
    ).all()
    assert len(rows) == 1


def test_league_configured_limit_overrides_default(db_session: Session) -> None:
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, team = _build_league_round_and_lineup(db_session, fixture)
    rules = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == fantasy_round.league_id)
    ).one()
    rules.max_automatic_substitutions = 0
    db_session.commit()

    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()

    row = get_effective_lineup(db_session, round_id=fantasy_round.id, fantasy_team_id=team.id)
    assert row is not None
    assert row.substitutions_json == []
    # Nessuna sostituzione applicata: i ruoli restano quelli della formazione
    # salvata (modulo comunque valido), ma Fornals resta titolare senza voto.
    assert row.module_valid is True
    fornals = db_session.scalars(select(Athlete).where(Athlete.provider_id == 1697)).one()
    assert str(fornals.id) in row.effective_starter_ids
    assert len(row.skipped_json) == len(WEST_HAM_BENCH)
    assert all(item["reason"] == "limit_reached" for item in row.skipped_json)
