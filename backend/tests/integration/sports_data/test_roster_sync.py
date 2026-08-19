"""Integration tests for sports roster sync idempotency (EP04-03)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from observability.metrics import get_metrics, reset_metrics
from sports_data.catalog.models import Club
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete, SquadMembership, Transfer
from sports_data.roster.sync import (
    ROSTER_SYNC_ENTITIES_TOTAL,
    PlayersBatch,
    SquadBatch,
    sync_roster,
)

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


@pytest.fixture(autouse=True)
def clean_roster_tables(session: Session) -> None:
    """Isola i test roster: il modulo condivide DB e commit tra casi."""
    session.execute(delete(SquadMembership))
    session.execute(delete(Transfer))
    session.execute(delete(Athlete))
    session.commit()


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


def _fixture_roster_batches() -> tuple[list[SquadBatch], list[PlayersBatch], list]:
    squads_wolves = parse_envelope(
        _load("reference/players_squads_wolves.json"),
        endpoint="/players/squads",
        http_status=200,
    )
    squads_chelsea = parse_envelope(
        _load("reference/players_squads_chelsea.json"),
        endpoint="/players/squads",
        http_status=200,
    )
    players_wolves = parse_envelope(
        _load("reference/players_wolves.json"),
        endpoint="/players",
        http_status=200,
    )
    transfers = parse_envelope(
        _load("reference/transfers_sample.json"),
        endpoint="/transfers",
        http_status=200,
    )
    squad_batches = [
        SquadBatch(
            envelope=squads_wolves,
            club_provider_id=39,
            competition_provider_id=39,
            season_year=2026,
        ),
        SquadBatch(
            envelope=squads_chelsea,
            club_provider_id=49,
            competition_provider_id=39,
            season_year=2026,
        ),
    ]
    players_batches = [
        PlayersBatch(envelope=players_wolves, club_provider_id=39, season_year=2026),
    ]
    return squad_batches, players_batches, [transfers]


def test_roster_sync_idempotent_stable_uuids(session: Session) -> None:
    reset_metrics()
    _seed_catalog(session)
    session.commit()

    squad_batches, players_batches, transfers = _fixture_roster_batches()
    first = sync_roster(
        session,
        squad_batches=squad_batches,
        players_batches=players_batches,
        transfers_envelopes=transfers,
    )
    session.commit()

    assert first.counters.athletes_created >= 5
    assert first.counters.memberships_created >= 6
    assert first.counters.transfers_created == 2

    jimenez = session.execute(
        select(Athlete).where(Athlete.provider_id == 2887),
    ).scalar_one()
    jimenez_id = jimenez.id

    second = sync_roster(
        session,
        squad_batches=squad_batches,
        players_batches=players_batches,
        transfers_envelopes=transfers,
    )
    session.commit()

    jimenez_after = session.execute(
        select(Athlete).where(Athlete.provider_id == 2887),
    ).scalar_one()
    assert jimenez_after.id == jimenez_id
    assert second.counters.athletes_created == 0
    assert second.counters.memberships_created == 0
    assert second.counters.transfers_created == 0
    assert second.counters.transfers_unchanged == 2

    metrics = get_metrics()
    assert (
        metrics.get_counter(
            ROSTER_SYNC_ENTITIES_TOTAL,
            labels={"provider": "api-football-v3", "entity": "athletes", "result": "unchanged"},
        )
        >= 1
    )


def test_team_change_preserves_historical_membership(session: Session) -> None:
    _seed_catalog(session)
    session.commit()

    squad_batches, players_batches, transfers = _fixture_roster_batches()
    sync_roster(
        session,
        squad_batches=[squad_batches[0]],
        players_batches=players_batches,
        transfers_envelopes=[],
    )
    session.commit()

    wolves = session.execute(select(Club).where(Club.provider_id == 39)).scalar_one()
    jimenez = session.execute(select(Athlete).where(Athlete.provider_id == 2887)).scalar_one()
    wolves_membership = session.execute(
        select(SquadMembership).where(
            SquadMembership.athlete_id == jimenez.id,
            SquadMembership.club_id == wolves.id,
        ),
    ).scalar_one()
    assert wolves_membership.is_active is True

    sync_roster(
        session,
        squad_batches=squad_batches,
        players_batches=[],
        transfers_envelopes=transfers,
    )
    session.commit()

    session.refresh(wolves_membership)
    assert wolves_membership.is_active is False
    assert wolves_membership.ended_at is not None

    chelsea = session.execute(select(Club).where(Club.provider_id == 49)).scalar_one()
    chelsea_membership = session.execute(
        select(SquadMembership).where(
            SquadMembership.athlete_id == jimenez.id,
            SquadMembership.club_id == chelsea.id,
        ),
    ).scalar_one()
    assert chelsea_membership.is_active is True

    assert session.execute(select(func.count()).select_from(SquadMembership)).scalar_one() >= 2
    loan_transfer = session.execute(
        select(Transfer).where(Transfer.transfer_type == "Loan"),
    ).scalar_one()
    assert loan_transfer.requires_admin_review is True


def test_roster_sync_skips_unknown_clubs(session: Session) -> None:
    _seed_catalog(session)
    session.commit()

    payload = {
        "errors": [],
        "get": "players/squads",
        "parameters": {"team": "999999"},
        "paging": {"current": 1, "total": 1},
        "results": 1,
        "response": [
            {
                "team": {"id": 999999, "name": "Club Fantasma"},
                "players": [{"id": 888001, "name": "Giocatore Test", "position": "Midfielder"}],
            }
        ],
    }
    envelope = parse_envelope(payload, endpoint="/players/squads", http_status=200)
    result = sync_roster(
        session,
        squad_batches=[
            SquadBatch(
                envelope=envelope,
                club_provider_id=999999,
                competition_provider_id=39,
                season_year=2026,
            ),
        ],
    )
    session.commit()
    assert result.counters.memberships_skipped_missing_club == 1
    assert (
        session.execute(select(Athlete).where(Athlete.provider_id == 888001)).scalar_one_or_none()
        is None
    )
