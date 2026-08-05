"""Integration tests for sports catalog sync idempotency (EP04-02)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leagues.models.competition import Competition
from observability.metrics import get_metrics, reset_metrics
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.catalog.sync import (
    CATALOG_SYNC_ENTITIES_TOTAL,
    TeamsBatch,
    sync_catalog,
)
from sports_data.provider.envelope import parse_envelope

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def test_catalog_sync_idempotent_stable_provider_ids(session: Session) -> None:
    reset_metrics()
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    teams = parse_envelope(_load("reference/teams.json"), endpoint="/teams", http_status=200)
    batches = [
        TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026),
    ]

    first = sync_catalog(session, leagues_envelope=leagues, teams_batches=batches)
    session.commit()

    competitions = session.scalars(select(Competition).order_by(Competition.provider_id)).all()
    assert {c.provider_id for c in competitions} >= {39, 140, 135, 78, 61}
    ids_after_first = {c.provider_id: c.id for c in competitions}

    seasons = session.scalars(select(SportSeason)).all()
    assert len(seasons) == 5
    assert all(s.year == 2026 and s.is_current for s in seasons)

    clubs_count = session.execute(select(func.count()).select_from(Club)).scalar_one()
    assert clubs_count == 36
    memberships = session.execute(
        select(func.count()).select_from(CompetitionSeasonClub),
    ).scalar_one()
    assert memberships == 36
    competition_ops = (
        first.counters.competitions_created
        + first.counters.competitions_updated
        + first.counters.competitions_unchanged
    )
    assert competition_ops == 5
    assert first.counters.seasons_created == 5
    assert first.counters.clubs_created == 36
    # Seed EP03-01 già inserisce le 5 competizioni MVP: sync non deve ricrearle.
    assert first.counters.competitions_created == 0

    second = sync_catalog(session, leagues_envelope=leagues, teams_batches=batches)
    session.commit()

    competitions2 = session.scalars(select(Competition)).all()
    ids_after_second = {c.provider_id: c.id for c in competitions2}
    assert ids_after_second == ids_after_first

    assert session.execute(select(func.count()).select_from(SportSeason)).scalar_one() == 5
    assert session.execute(select(func.count()).select_from(Club)).scalar_one() == 36
    assert (
        session.execute(select(func.count()).select_from(CompetitionSeasonClub)).scalar_one() == 36
    )
    assert second.counters.competitions_created == 0
    assert second.counters.seasons_created == 0
    assert second.counters.clubs_created == 0
    assert second.counters.memberships_created == 0
    assert second.counters.competitions_unchanged == 5
    assert second.counters.clubs_unchanged == 36

    metrics = get_metrics()
    assert (
        metrics.get_counter(
            CATALOG_SYNC_ENTITIES_TOTAL,
            labels={"provider": "api-football-v3", "entity": "clubs", "result": "unchanged"},
        )
        >= 36
    )


def test_catalog_sync_updates_name_without_changing_uuid(session: Session) -> None:
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    sync_catalog(session, leagues_envelope=leagues, teams_batches=[])
    session.commit()
    original = session.execute(
        select(Competition).where(Competition.provider_id == 39),
    ).scalar_one()
    original_id = original.id

    altered = json.loads(json.dumps(_load("reference/leagues.json")))
    for row in altered["response"]:
        if row["league"]["id"] == 39:
            row["league"]["name"] = "Premier League Renamed"
    envelope = parse_envelope(altered, endpoint="/leagues", http_status=200)
    result = sync_catalog(session, leagues_envelope=envelope, teams_batches=[])
    session.commit()

    updated = session.execute(
        select(Competition).where(Competition.provider_id == 39),
    ).scalar_one()
    assert updated.id == original_id
    assert updated.name == "Premier League Renamed"
    assert result.counters.competitions_updated == 1


def test_catalog_sync_skips_national_clubs(session: Session) -> None:
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    sync_catalog(session, leagues_envelope=leagues, teams_batches=[])
    session.commit()

    teams_payload = {
        "get": "teams",
        "parameters": {"league": "39", "season": "2026"},
        "errors": [],
        "results": 2,
        "paging": {"current": 1, "total": 1},
        "response": [
            {"team": {"id": 900001, "name": "Club Test MVP", "national": False}},
            {"team": {"id": 900002, "name": "Nazionale Test", "national": True}},
        ],
    }
    teams = parse_envelope(teams_payload, endpoint="/teams", http_status=200)
    result = sync_catalog(
        session,
        teams_batches=[
            TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026),
        ],
    )
    session.commit()
    assert result.counters.clubs_created == 1
    assert result.counters.clubs_skipped_national == 1
    assert (
        session.execute(select(Club).where(Club.provider_id == 900001)).scalar_one_or_none()
        is not None
    )
    assert (
        session.execute(select(Club).where(Club.provider_id == 900002)).scalar_one_or_none()
        is None
    )
