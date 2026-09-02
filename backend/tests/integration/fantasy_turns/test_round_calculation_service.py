"""Integration tests for the unified round-calculation engine (EP-turni-calcolo)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRoundHomologationStatus, LineupAutoResolutionSource
from database.session import create_session_factory
from fantasy_lineups.models import LineupSubmission
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_turns.live_pipeline import process_live_fantasy_rounds
from fantasy_turns.models import FantasyRound
from fantasy_turns.round_calculation_service import calculate_league_round
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from sports_data.fixtures.models import Fixture
from tests.integration.fantasy_turns.test_fantasy_turns import (
    _promote_to_operator,
    _register_and_login,
)
from tests.integration.leagues.test_scoring_service import (
    _build_two_team_round,
    _seed_catalog,
    _sync_match,
)


@pytest.fixture()
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _prepare_scenario(db_session: Session) -> tuple[FantasyRound, dict, Fixture]:
    """Sincronizza la fixture reale e valuta i rating: da chiamare **una sola
    volta per modulo** (i test condividono lo stesso DB senza rollback tra
    l'uno e l'altro, e omologare un turno blocca per sempre il ricalcolo dei
    rating di quella fixture, in qualunque lega — `assert_fixture_not_homologated`).
    I test successivi devono riusare `_existing_fixture` invece di richiamare
    questa funzione."""
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    return fantasy_round, teams, fixture


def _existing_fixture(db_session: Session) -> Fixture:
    return db_session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()


def _drop_submission(db_session: Session, round_id, team_id) -> None:
    submission = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == round_id,
            LineupSubmission.fantasy_team_id == team_id,
        )
    ).one()
    db_session.delete(submission)
    db_session.commit()


def _slot(db_session: Session, league_id) -> LeagueCalendarSlot:
    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == league_id)
    ).one()
    return db_session.scalars(
        select(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
    ).one()


def test_calculates_and_homologates_a_round_with_a_missing_lineup(db_session: Session) -> None:
    """Riproduce esattamente il bug reale osservato su 'Test lega': turno con
    partite concluse ma un fantallenatore senza formazione -> prima di questa
    feature restava bloccato per sempre; ora si risolve a 0 punti e omologa."""
    fantasy_round, teams, _fixture = _prepare_scenario(db_session)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)

    result = calculate_league_round(
        db_session,
        round_id=fantasy_round.id,
        league_id=fantasy_round.league_id,
        actor_id=None,
        automatic=False,
    )
    db_session.commit()

    assert result.fallback is not None
    assert result.fallback.resolved_as_zero == 1
    assert result.result_final is True
    assert result.homologated is True

    refreshed = db_session.get(FantasyRound, fantasy_round.id)
    assert refreshed is not None
    assert refreshed.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED

    slot = _slot(db_session, fantasy_round.league_id)
    assert slot.result_final is True
    assert slot.away_score == 0.0  # Chelsea: nessuna formazione -> 0 punti
    assert slot.outcome in {"home", "draw"}  # mai "away": West Ham ha voti reali > 0

    chelsea_submission = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == fantasy_round.id,
            LineupSubmission.fantasy_team_id == teams["chelsea"].id,
        )
    ).one()
    assert chelsea_submission.auto_resolution_source == LineupAutoResolutionSource.ZERO_FALLBACK
    assert chelsea_submission.players == []
    # Idempotenza del fallback in sé (senza toccare l'omologazione, che una
    # volta scattata blocca ogni ricalcolo dei rating della fixture) è già
    # coperta da test_fallback_service.py — chiamare due volte qui
    # richiederebbe una correzione (apply_round_correction), fuori scope.


def test_the_automatic_job_calls_the_same_engine_as_the_manual_command(
    db_session: Session,
) -> None:
    """EP-turni-calcolo requisito 9: nessuna logica divergente tra job e comando manuale.

    Riusa la fixture reale già sincronizzata e valutata dal test precedente
    (stesso modulo, stesso DB) su una NUOVA lega — evita di richiamare di
    nuovo `compute_fixture_ratings`, bloccato una volta che una qualsiasi
    lega ha già omologato un turno su questa fixture.
    """
    fixture = _existing_fixture(db_session)
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)

    pipeline_result = process_live_fantasy_rounds(db_session)
    db_session.commit()

    assert pipeline_result.rounds_processed == 1
    assert pipeline_result.rounds_finalized == 1

    refreshed = db_session.get(FantasyRound, fantasy_round.id)
    assert refreshed is not None
    assert refreshed.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED

    chelsea_submission = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == fantasy_round.id,
            LineupSubmission.fantasy_team_id == teams["chelsea"].id,
        )
    ).one()
    assert chelsea_submission.auto_resolution_source == LineupAutoResolutionSource.ZERO_FALLBACK


def test_calculate_round_endpoint_rejects_non_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    token, _user_id = _register_and_login(client, "calcola-giornata.member@example.com")
    fixture = _existing_fixture(db_session)
    fantasy_round, _teams = _build_two_team_round(db_session, fixture)

    response = client.post(
        f"/leagues/{fantasy_round.league_id}/turni/{fantasy_round.id}/calcola-giornata",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_calculate_round_endpoint_matches_the_service_result_for_an_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    token, user_id = _register_and_login(client, "calcola-giornata.operator@example.com")
    _promote_to_operator(db_session, user_id)
    fixture = _existing_fixture(db_session)
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)

    response = client.post(
        f"/leagues/{fantasy_round.league_id}/turni/{fantasy_round.id}/calcola-giornata",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["roundId"] == str(fantasy_round.id)
    assert body["resultFinal"] is True
    assert body["homologated"] is True
    assert body["fallbackResolvedAsZero"] == 1

    # La chiamata HTTP ha omologato tramite una sessione DB separata da
    # db_session: bisogna scartare la identity map locale prima di rileggere.
    db_session.expire_all()
    refreshed = db_session.get(FantasyRound, fantasy_round.id)
    assert refreshed is not None
    assert refreshed.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED
