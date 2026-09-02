"""Unit tests for provider position → P–D–C–A mapping (EP04-04)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from database.enums import FantasyRole
from sports_data.listone.mapping import (
    MAPPING_VERSION,
    map_provider_position_to_role,
    normalize_provider_position,
    require_valid_role,
)
from sports_data.provider.envelope import parse_envelope
from sports_data.provider.mapping import map_squad_memberships

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Goalkeeper", FantasyRole.P),
        ("goalkeeper", FantasyRole.P),
        ("G", FantasyRole.P),
        ("Defender", FantasyRole.D),
        ("Midfielder", FantasyRole.C),
        ("Attacker", FantasyRole.A),
        ("Forward", FantasyRole.A),
        ("F", FantasyRole.A),
        ("P", FantasyRole.P),
        (None, None),
        ("", None),
        ("Wing Back", None),
    ],
)
def test_map_provider_position_to_role(raw: str | None, expected: FantasyRole | None) -> None:
    assert map_provider_position_to_role(raw) == expected


def test_mapping_version_is_stable() -> None:
    assert MAPPING_VERSION.startswith("v")


def test_require_valid_role_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Ruolo non valido"):
        require_valid_role("X")


def test_normalize_collapses_whitespace() -> None:
    assert normalize_provider_position("  Mid  Fielder ") == "mid fielder"


def test_fixture_squad_positions_all_map() -> None:
    envelope = parse_envelope(
        _load("reference/players_squads_wolves.json"),
        endpoint="/players/squads",
    )
    rows = map_squad_memberships(envelope, competition_provider_id=39, season_year=2026)
    mapped = [map_provider_position_to_role(r.provider_position_raw) for r in rows]
    assert None not in mapped
    assert mapped == [
        FantasyRole.P,
        FantasyRole.D,
        FantasyRole.C,
        FantasyRole.A,
        FantasyRole.A,
    ]


def test_mapping_idempotent_on_fixture_payload() -> None:
    envelope = parse_envelope(
        _load("reference/players_squads_wolves.json"),
        endpoint="/players/squads",
    )
    first = [
        map_provider_position_to_role(r.provider_position_raw)
        for r in map_squad_memberships(envelope, competition_provider_id=39, season_year=2026)
    ]
    second = [
        map_provider_position_to_role(r.provider_position_raw)
        for r in map_squad_memberships(envelope, competition_provider_id=39, season_year=2026)
    ]
    assert first == second
