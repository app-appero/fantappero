"""Unit tests for catalog mapping (seasons) — EP04-02."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sports_data.provider.envelope import parse_envelope
from sports_data.provider.mapping import map_clubs, map_seasons
from sports_data.provider.types import ProviderEnvelope, ProviderPaging

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def test_map_seasons_from_leagues_fixture() -> None:
    envelope = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues")
    seasons = map_seasons(envelope)
    assert len(seasons) == 5
    by_league = {s.competition_provider_id: s for s in seasons}
    assert set(by_league) == {39, 140, 135, 78, 61}
    premier = by_league[39]
    assert premier.year == 2026
    assert premier.is_current is True
    assert premier.start_date == date(2026, 8, 21)
    assert premier.end_date == date(2027, 5, 30)
    assert premier.coverage_events is False
    assert premier.coverage_predictions is True
    assert premier.coverage_standings is True


def test_map_seasons_idempotent() -> None:
    payload = _load("reference/leagues.json")
    a = map_seasons(parse_envelope(payload, endpoint="/leagues"))
    b = map_seasons(parse_envelope(payload, endpoint="/leagues"))
    assert [(s.competition_provider_id, s.year) for s in a] == [
        (s.competition_provider_id, s.year) for s in b
    ]


def test_map_clubs_marks_national_teams() -> None:
    envelope = ProviderEnvelope(
        endpoint="/teams",
        parameters={"league": "39", "season": "2026"},
        errors=[],
        results=2,
        paging=ProviderPaging(current=1, total=1),
        response=[
            {
                "team": {
                    "id": 50,
                    "name": "Manchester City",
                    "national": False,
                    "code": "MCI",
                    "logo": "https://media.api-sports.io/football/teams/50.png",
                }
            },
            {"team": {"id": 1, "name": "Belgium", "national": True, "code": "BEL"}},
        ],
    )
    clubs = map_clubs(envelope)
    assert len(clubs) == 2
    assert clubs[0].national is False
    assert clubs[1].national is True
    assert clubs[0].logo_url == "https://media.api-sports.io/football/teams/50.png"
    assert clubs[1].logo_url is None
