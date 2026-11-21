"""Stato del mercato a turno in corso (decisione di Rosario del 21/11/2026).

Dal primo blocco del turno all'omologazione rosa, aste e scambi sono fermi: ``GET …/mercato/
stato`` lo dice con ``marketBlockedReason: "round_in_progress"`` e le app scrivono «Mercato
fermo: turno in corso» invece di «Mercato aperto». Il turno conta anche a interruttore spento:
blocca pure gli scambi, che l'interruttore lascia passare.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyTurnKind, FantasyTurnStatus
from database.session import create_session_factory
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league import League
from mail.capture import get_captured_emails


def _register_and_login(client: TestClient, email: str) -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"]


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_round(db_session: Session, league_id: str, *, cutoff: datetime) -> FantasyRound:
    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=cutoff - timedelta(days=1),
        window_end_at=cutoff + timedelta(days=2),
        cutoff_at=cutoff,
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now - timedelta(days=1),
    )
    db_session.add(fantasy_round)
    db_session.commit()
    return fantasy_round


def _gate(client: TestClient, league_id: str, token: str) -> dict[str, object]:
    response = client.get(
        f"/leagues/{league_id}/mercato/stato", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_gate_reports_the_round_in_progress_from_the_first_lock(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token = _register_and_login(client, "gate.round.progress@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Mercato Turno")
    assert _gate(client, league_id, token)["marketBlockedReason"] is None

    # Calcio d'inizio fra 10 minuti, margine di lega 15: il primo blocco è già passato.
    _add_round(db_session, league_id, cutoff=datetime.now(UTC) + timedelta(minutes=10))

    gate = _gate(client, league_id, token)
    assert gate["marketOpen"] is True
    assert gate["marketBlockedReason"] == "round_in_progress"


def test_round_in_progress_wins_over_the_closed_switch(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """A interruttore spento «mercato chiuso, restano gli scambi» sarebbe falso: il turno in
    corso ferma anche gli scambi."""
    token = _register_and_login(client, "gate.round.closed@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Mercato Turno Chiuso")
    db_session.execute(update(League).where(League.id == UUID(league_id)).values(market_open=False))
    db_session.commit()
    assert _gate(client, league_id, token)["marketBlockedReason"] == "market_closed"

    fantasy_round = _add_round(db_session, league_id, cutoff=datetime.now(UTC) - timedelta(hours=1))

    gate = _gate(client, league_id, token)
    assert gate["marketOpen"] is False
    assert gate["marketBlockedReason"] == "round_in_progress"

    # Omologato il turno torna il motivo dell'interruttore.
    fantasy_round.homologated_at = datetime.now(UTC)
    db_session.commit()
    assert _gate(client, league_id, token)["marketBlockedReason"] == "market_closed"
