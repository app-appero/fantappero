"""Integration tests for the admin round-calculation endpoints (EP-turni-calcolo)."""

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
from fantasy_turns.models import FantasyRound
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


def _prepare_fixture(db_session: Session) -> Fixture:
    """Sincronizza e valuta la fixture reale — una sola volta per modulo,
    stesso vincolo di `test_round_calculation_service.py` (omologare blocca
    per sempre il ricalcolo dei rating di quella fixture)."""
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()
    return fixture


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


def test_calculate_current_rounds_endpoint_rejects_non_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    token, _user_id = _register_and_login(client, "admin-calcola.member@example.com")
    response = client.post(
        "/admin/turni/calcola-giornata",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_calculate_current_rounds_endpoint_finalizes_a_round_with_missing_lineup(
    client: TestClient,
    db_session: Session,
) -> None:
    token, user_id = _register_and_login(client, "admin-calcola.operator@example.com")
    _promote_to_operator(db_session, user_id)
    fixture = _prepare_fixture(db_session)
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)

    response = client.post(
        "/admin/turni/calcola-giornata",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["roundsProcessed"] == 1
    assert body["roundsFinalized"] == 1

    db_session.expire_all()
    refreshed = db_session.get(FantasyRound, fantasy_round.id)
    assert refreshed is not None
    assert refreshed.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED


def test_historical_repair_endpoint_rejects_non_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    token, _user_id = _register_and_login(client, "admin-ricalcola.member@example.com")
    response = client.post(
        "/admin/turni/ricalcola-storico",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert response.status_code == 403


def test_historical_repair_endpoint_repairs_a_round_stuck_provisional_forever(
    client: TestClient,
    db_session: Session,
) -> None:
    """Riproduce lo scenario reale osservato su 'Test lega': turno con
    formazione mancante mai risolto (mai omologato) -> "Ricalcola storico"
    lo trova e lo chiude, esattamente come farebbe l'operatore dal pannello.
    """
    token, user_id = _register_and_login(client, "admin-ricalcola.operator@example.com")
    _promote_to_operator(db_session, user_id)
    fixture = _existing_fixture(db_session)
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)
    # Nessun calcolo eseguito: il turno resta "provvisorio" per sempre,
    # esattamente come nei dati reali prima di questa feature.

    response = client.post(
        "/admin/turni/ricalcola-storico",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Recupero storico formazioni mancanti — test"},
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["jobId"]

    # In ambiente di test Celery gira in modalità eager (task_always_eager):
    # il job è già concluso quando la chiamata HTTP torna.
    progress = client.get(
        f"/admin/turni/ricalcola-storico/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert progress.status_code == 200, progress.text
    progress_body = progress.json()
    assert progress_body["status"] == "completed"
    assert progress_body["result"]["roundsRepaired"] == 1
    assert progress_body["result"]["roundsFailed"] == 0

    db_session.expire_all()
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
