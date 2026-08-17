"""Integration tests for persisted statistical ratings (EP07-01)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from fantasy_ratings.bonus import reconstruct_total_from_stored
from fantasy_ratings.formula import reconstruct_raw_from_stored
from fantasy_ratings.models import PlayerMatchRating
from fantasy_ratings.service import compute_fixture_ratings
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
    PlayerMatchStat,
)
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
MATCH = DATASET / "matches" / "39" / "1035055"


@pytest.fixture(autouse=True)
def clean_tables(session: Session) -> None:
    session.execute(delete(PlayerMatchRating))
    session.execute(delete(OfficialLineupEntry))
    session.execute(delete(OfficialLineup))
    session.execute(delete(PlayerMatchStat))
    session.execute(delete(MatchEvent))
    session.execute(delete(Fixture))
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


def test_compute_ratings_idempotent_and_reconstructible(session: Session) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync_match(session)
    session.commit()

    first = compute_fixture_ratings(session, fixture_id=fixture.id)
    session.commit()
    assert first.counters.created >= 20
    assert first.counters.updated == 0
    assert first.counters.unchanged == 0

    count_after_first = session.execute(
        select(func.count()).select_from(PlayerMatchRating)
    ).scalar_one()
    assert count_after_first == first.counters.created

    second = compute_fixture_ratings(session, fixture_id=fixture.id)
    session.commit()
    assert second.counters.created == 0
    assert second.counters.updated == 0
    assert second.counters.unchanged == count_after_first
    assert (
        session.execute(select(func.count()).select_from(PlayerMatchRating)).scalar_one()
        == count_after_first
    )

    areola = session.execute(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id == fixture.id,
            PlayerMatchRating.athlete_provider_id == 253,
        )
    ).scalar_one()
    assert areola.formula_version == "beta-v0.1"
    assert areola.eligible is True
    assert areola.display == 6.5
    assert areola.raw == pytest.approx(6.732, abs=1e-3)
    assert areola.formula_json["base"] == 6.0
    assert areola.input_json["athlete_provider_id"] == 253
    assert areola.components_json
    rebuilt = reconstruct_raw_from_stored(areola.formula_json, areola.components_json)
    assert rebuilt == pytest.approx(areola.raw)

    # EP07-03: Areola ha parato un rigore (+3) e subito un gol (-1) da portiere.
    assert areola.bonus_config_version == "bonus-beta-v0.1"
    assert {item["id"]: item["contribution"] for item in areola.bonus_malus_json} == {
        "penalty_saved": 3.0,
        "goalkeeper_goal_conceded": -1.0,
    }
    assert areola.bonus_malus_total == pytest.approx(2.0)
    assert areola.fantasy_score == pytest.approx(8.5)
    rebuilt_bonus = reconstruct_total_from_stored(areola.bonus_malus_json)
    assert rebuilt_bonus == pytest.approx(areola.bonus_malus_total)

    fornals = session.execute(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id == fixture.id,
            PlayerMatchRating.athlete_provider_id == 1697,
        )
    ).scalar_one()
    assert fornals.eligible is False
    assert fornals.display is None
    assert fornals.eligibility_reason == "under_threshold_no_relevant_event"
    assert fornals.input_json["entered_in_stoppage"] is False
    assert fornals.formula_json["minutes_threshold"] == 15


def test_bonus_malus_exposed_via_api_and_stable_on_recompute(session: Session) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync_match(session)
    session.commit()

    from fantasy_ratings.service import FantasyRatingService

    service = FantasyRatingService(session)
    service.compute_for_fixture(fixture_id=fixture.id)
    session.commit()

    votes = {row.athlete_provider_id: row for row in service.list_for_fixture(fixture.id)}

    ward_prowse = votes[2938]
    assert ward_prowse.bonus_malus == [
        {"id": "assist", "count": 2, "unit_value": 1.0, "contribution": 2.0}
    ]
    assert ward_prowse.bonus_malus_total == pytest.approx(2.0)
    assert ward_prowse.fantasy_score == pytest.approx(ward_prowse.display + 2.0)

    aguerd = votes[21694]
    assert {item["id"] for item in aguerd.bonus_malus} == {"goal", "red_card"}
    assert aguerd.bonus_malus_total == pytest.approx(2.0)

    fornals = votes[1697]
    assert fornals.eligible is False
    assert fornals.bonus_malus == []
    assert fornals.bonus_malus_total == pytest.approx(0.0)
    assert fornals.fantasy_score is None

    # Ricalcolo: nessuna riga aggiornata, bonus/malus persistiti identici.
    second = service.compute_for_fixture(fixture_id=fixture.id)
    assert second.updated == 0
    assert second.created == 0
    votes_again = {row.athlete_provider_id: row for row in service.list_for_fixture(fixture.id)}
    assert votes_again[2938].bonus_malus == ward_prowse.bonus_malus
    assert votes_again[2938].fantasy_score == pytest.approx(ward_prowse.fantasy_score)


def test_minutes_threshold_overlay_does_not_rewrite_row(session: Session) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync_match(session)
    session.commit()

    compute_fixture_ratings(session, fixture_id=fixture.id)
    session.commit()

    from fantasy_ratings.service import FantasyRatingService

    service = FantasyRatingService(session)
    default_votes = {row.athlete_provider_id: row for row in service.list_for_fixture(fixture.id)}
    overlay = {
        row.athlete_provider_id: row
        for row in service.list_for_fixture(fixture.id, minutes_threshold=10)
    }
    assert default_votes[1697].eligible is False
    assert default_votes[1697].display is None
    assert overlay[1697].eligible is True
    assert overlay[1697].display is not None
    assert overlay[1697].formula["minutes_threshold"] == 10

    stored = session.execute(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id == fixture.id,
            PlayerMatchRating.athlete_provider_id == 1697,
        )
    ).scalar_one()
    assert stored.eligible is False
    assert stored.formula_json["minutes_threshold"] == 15


def test_compute_with_higher_threshold_marks_exact_fifteen_senza_voto(
    session: Session,
) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync_match(session)
    session.commit()

    result = compute_fixture_ratings(session, fixture_id=fixture.id, minutes_threshold=16)
    session.commit()
    assert result.counters.created >= 20

    madueke = session.execute(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id == fixture.id,
            PlayerMatchRating.athlete_provider_id == 136723,
        )
    ).scalar_one()
    assert madueke.minutes == 15
    assert madueke.eligible is False
    assert madueke.display is None
    assert madueke.formula_json["minutes_threshold"] == 16

    again = compute_fixture_ratings(session, fixture_id=fixture.id, minutes_threshold=16)
    session.commit()
    assert again.counters.created == 0
    assert again.counters.updated == 0
    assert again.counters.unchanged == result.counters.created
