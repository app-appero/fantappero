"""Integration tests for player availability sync idempotency (OQ-11)."""

from __future__ import annotations

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from database.enums import PlayerAvailabilityCategory
from sports_data.availability.models import PlayerAvailability
from sports_data.availability.sync import (
    AvailabilitySyncCounters,
    is_confirmed_unavailable,
    sync_player_availabilities,
)
from sports_data.provider.envelope import parse_envelope

COMPETITION_ID = 135
SEASON_YEAR = 2026


@pytest.fixture(autouse=True)
def clean_availability_table(session: Session) -> None:
    session.execute(delete(PlayerAvailability))
    session.commit()


def _envelope(rows: list[dict]):
    payload = {
        "get": "injuries",
        "parameters": {},
        "errors": [],
        "results": len(rows),
        "paging": {"current": 1, "total": 1},
        "response": rows,
    }
    return parse_envelope(payload, endpoint="/injuries", http_status=200)


def _row(player_id: int, reason: str, fixture_id: int = 999001, status: str = "Missing Fixture") -> dict:
    return {
        "player": {"id": player_id, "name": f"Player {player_id}", "type": status, "reason": reason},
        "team": {"id": 487, "name": "Example FC"},
        "fixture": {"id": fixture_id},
        "league": {"id": COMPETITION_ID, "season": SEASON_YEAR},
    }


def test_sync_creates_one_row_per_provider_key(session: Session) -> None:
    envelope = _envelope([_row(111, "Knee Injury"), _row(222, "Red Card")])
    counters = sync_player_availabilities(
        session,
        envelope,
        competition_provider_id=COMPETITION_ID,
        season_year=SEASON_YEAR,
    )
    session.commit()

    assert counters.created == 2
    rows = session.query(PlayerAvailability).all()
    assert len(rows) == 2
    categories = {row.athlete_provider_id: row.category for row in rows}
    assert categories[111] == PlayerAvailabilityCategory.INJURY.value
    assert categories[222] == PlayerAvailabilityCategory.SUSPENSION.value


def test_sync_is_idempotent_on_unchanged_rows(session: Session) -> None:
    envelope = _envelope([_row(111, "Knee Injury")])
    sync_player_availabilities(
        session, envelope, competition_provider_id=COMPETITION_ID, season_year=SEASON_YEAR
    )
    session.commit()

    counters = AvailabilitySyncCounters()
    sync_player_availabilities(
        session,
        envelope,
        competition_provider_id=COMPETITION_ID,
        season_year=SEASON_YEAR,
        counters=counters,
    )
    session.commit()

    assert counters.created == 0
    assert counters.unchanged == 1
    assert session.query(PlayerAvailability).count() == 1


def test_sync_updates_when_reason_changes(session: Session) -> None:
    first = _envelope([_row(111, "Knee Injury")])
    sync_player_availabilities(
        session, first, competition_provider_id=COMPETITION_ID, season_year=SEASON_YEAR
    )
    session.commit()

    second = _envelope([_row(111, "Thigh Injury")])
    counters = AvailabilitySyncCounters()
    sync_player_availabilities(
        session,
        second,
        competition_provider_id=COMPETITION_ID,
        season_year=SEASON_YEAR,
        counters=counters,
    )
    session.commit()

    assert counters.updated == 1
    row = session.query(PlayerAvailability).one()
    assert row.reason_raw == "Thigh Injury"


def test_is_confirmed_unavailable_returns_none_when_no_record(session: Session) -> None:
    """Nessun record = sconosciuto, mai 'disponibile' (caso reale Bordon, OQ-11)."""
    result = is_confirmed_unavailable(
        session,
        athlete_provider_id=999999,
        competition_provider_id=COMPETITION_ID,
        season_year=SEASON_YEAR,
    )
    assert result is None


def test_is_confirmed_unavailable_returns_the_record_when_present(session: Session) -> None:
    envelope = _envelope([_row(111, "Knee Injury")])
    sync_player_availabilities(
        session, envelope, competition_provider_id=COMPETITION_ID, season_year=SEASON_YEAR
    )
    session.commit()

    result = is_confirmed_unavailable(
        session,
        athlete_provider_id=111,
        competition_provider_id=COMPETITION_ID,
        season_year=SEASON_YEAR,
    )
    assert result is not None
    assert result.category == PlayerAvailabilityCategory.INJURY.value
