"""Unit tests for roster mapping (EP04-03)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sports_data.provider.envelope import parse_envelope
from sports_data.provider.mapping import (
    map_athletes_from_players,
    map_squad_memberships,
    map_transfers,
)
from sports_data.provider.types import ProviderEnvelope, ProviderPaging

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def test_map_squad_memberships_from_fixture() -> None:
    envelope = parse_envelope(
        _load("reference/players_squads_wolves.json"),
        endpoint="/players/squads",
    )
    rows = map_squad_memberships(
        envelope,
        competition_provider_id=39,
        season_year=2026,
    )
    assert len(rows) == 5
    jimenez = next(r for r in rows if r.athlete_provider_id == 2887)
    assert jimenez.club_provider_id == 39
    assert jimenez.provider_position_raw == "Attacker"
    assert jimenez.shirt_number == 9
    # Il dataset di test non include il campo "photo": assente, non un placeholder.
    assert jimenez.photo_url is None


def test_map_squad_memberships_extracts_photo_when_the_provider_gives_one() -> None:
    envelope = ProviderEnvelope(
        endpoint="/players/squads",
        parameters={"team": "50"},
        errors=[],
        results=1,
        paging=ProviderPaging(current=1, total=1),
        response=[
            {
                "team": {"id": 50},
                "players": [
                    {
                        "id": 19012,
                        "name": "M. Bettinelli",
                        "number": 13,
                        "position": "Goalkeeper",
                        "photo": "https://media.api-sports.io/football/players/19012.png",
                    }
                ],
            }
        ],
    )
    rows = map_squad_memberships(envelope, competition_provider_id=39, season_year=2026)
    assert rows[0].photo_url == "https://media.api-sports.io/football/players/19012.png"


def test_map_athletes_from_players_fixture() -> None:
    envelope = parse_envelope(_load("reference/players_wolves.json"), endpoint="/players")
    athletes = map_athletes_from_players(envelope, league_ids=frozenset({39}))
    assert len(athletes) == 2
    patricio = next(a for a in athletes if a.provider_id == 2674)
    assert patricio.canonical_name == "Rui Patrício"
    assert patricio.nationality == "Portugal"
    assert patricio.birth_date == date(1988, 2, 15)
    # Idem qui: nessuna foto nel dataset curato, il campo resta None.
    assert patricio.photo_url is None


def test_map_transfers_fixture() -> None:
    envelope = parse_envelope(_load("reference/transfers_sample.json"), endpoint="/transfers")
    transfers = map_transfers(envelope)
    assert len(transfers) == 2
    free = next(t for t in transfers if t.transfer_type == "Free")
    assert free.transfer_date == date(2026, 1, 10)
    assert free.from_club_provider_id == 39
    assert free.to_club_provider_id == 49
    loan = next(t for t in transfers if t.transfer_type == "Loan")
    assert loan.to_club_provider_id == 48


def test_mapping_idempotent_on_same_payload() -> None:
    payload = _load("reference/players_squads_wolves.json")
    envelope = parse_envelope(payload, endpoint="/players/squads")
    first = map_squad_memberships(envelope, competition_provider_id=39, season_year=2026)
    second = map_squad_memberships(envelope, competition_provider_id=39, season_year=2026)
    assert [(r.athlete_provider_id, r.club_provider_id) for r in first] == [
        (r.athlete_provider_id, r.club_provider_id) for r in second
    ]


def test_map_transfers_skips_rows_without_date() -> None:
    envelope = ProviderEnvelope(
        endpoint="/transfers",
        parameters={"player": "1"},
        errors=[],
        results=1,
        paging=ProviderPaging(current=1, total=1),
        response=[
            {
                "player": {"id": 1, "name": "Test"},
                "transfers": [{"date": None, "type": "Free", "teams": {"in": {}, "out": {}}}],
            }
        ],
    )
    assert map_transfers(envelope) == []
