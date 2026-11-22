"""Campionato o coppa (1.3): lettura di ``/leagues`` e regola delle righe che contano.

Decisione di Rosario (22/11): media stagionale e Valore contano solo i campionati.
"""

from __future__ import annotations

import json
from pathlib import Path

from sports_data.provider.constants import MVP_LEAGUE_IDS
from sports_data.provider.envelope import parse_envelope
from sports_data.season_stats.competition_types import (
    COMPETITION_TYPE_CUP,
    COMPETITION_TYPE_LEAGUE,
    COMPETITION_TYPE_UNKNOWN,
    CompetitionTypeItem,
    competition_kind,
    is_championship,
    parse_competition_types,
)

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"

SERIE_B = 136
COPPA_ITALIA = 137
CHAMPIONS_LEAGUE = 2


def _league(provider_id: object, name: object, kind: object) -> dict[str, object]:
    return {"league": {"id": provider_id, "name": name, "type": kind}, "seasons": []}


def test_reads_the_type_from_the_real_leagues_payload() -> None:
    payload = json.loads((DATASET / "reference" / "leagues.json").read_text(encoding="utf-8"))
    items = parse_competition_types(parse_envelope(payload, endpoint="/leagues"))
    assert {item.provider_id for item in items} == set(MVP_LEAGUE_IDS)
    assert {item.type for item in items} == {COMPETITION_TYPE_LEAGUE}
    assert CompetitionTypeItem(provider_id=135, type="league", name="Serie A") in items


def test_reads_leagues_and_cups_and_skips_what_it_cannot_classify() -> None:
    envelope = parse_envelope(
        {
            "get": "leagues",
            "parameters": [],
            "errors": [],
            "results": 7,
            "paging": {"current": 1, "total": 1},
            "response": [
                _league(SERIE_B, "  Serie B  ", "League"),
                _league(COPPA_ITALIA, "Coppa Italia", "Cup"),
                _league(CHAMPIONS_LEAGUE, "UEFA Champions League", "cup"),
                _league(667, "Friendlies Clubs", "Friendly"),  # tipo che non conosciamo
                _league(None, "Senza id", "League"),
                _league(0, "Id zero", "Cup"),
                {"league": "non un oggetto"},
            ],
        },
        endpoint="/leagues",
    )
    items = parse_competition_types(envelope)
    assert sorted((item.provider_id, item.type, item.name) for item in items) == [
        (CHAMPIONS_LEAGUE, "cup", "UEFA Champions League"),
        (SERIE_B, "league", "Serie B"),
        (COPPA_ITALIA, "cup", "Coppa Italia"),
    ]


def test_championship_rule() -> None:
    types = {SERIE_B: "league", COPPA_ITALIA: "cup", CHAMPIONS_LEAGUE: "cup"}
    # I 5 campionati contano sempre, anche senza elenco o con un tipo strano.
    for provider_id in MVP_LEAGUE_IDS:
        assert is_championship(provider_id, types)
        assert is_championship(provider_id, {})
        assert is_championship(provider_id, {provider_id: "cup"})
    # Campionato fuori dai 5: conta se il tipo è noto.
    assert is_championship(SERIE_B, types)
    assert competition_kind(SERIE_B, types) == COMPETITION_TYPE_LEAGUE
    # Coppe: escluse.
    assert not is_championship(COPPA_ITALIA, types)
    assert competition_kind(COPPA_ITALIA, types) == COMPETITION_TYPE_CUP
    assert not is_championship(CHAMPIONS_LEAGUE, types)
    # Tipo sconosciuto (elenco vuoto, id assente, id 0): escluso.
    assert not is_championship(SERIE_B, {})
    assert competition_kind(SERIE_B, {}) == COMPETITION_TYPE_UNKNOWN
    assert not is_championship(999, types)
    assert not is_championship(0, types)
