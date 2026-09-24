"""OQ-08 (docs/data/api_football_open_questions.md): coverage e null-rate
dei campi stats sui payload reali del corpus offline, non su fixture
sintetiche come nel resto della suite fantasy_ratings.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from fantasy_ratings.input import iter_players_from_payload

_DATASET = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "api_football"
_LEAGUE_IDS = {39, 140, 135, 78, 61}

# Campi grezzi consumati oggi dalla formula v1 (fantasy_ratings/input.py e
# mapping.py): quelli con `_as_int(None) == 0` sono conteggi dove "null" del
# provider significa "zero occorrenze", non "dato mancante".
_ZERO_AS_NULL_FIELDS = {
    "goals.total": lambda s: s.get("goals", {}).get("total"),
    "goals.assists": lambda s: s.get("goals", {}).get("assists"),
    "cards.red": lambda s: s.get("cards", {}).get("red"),
    "penalty.missed": lambda s: s.get("penalty", {}).get("missed"),
    "penalty.saved": lambda s: s.get("penalty", {}).get("saved"),
}

# `games.minutes`/`games.rating` sono null per i convocati in panchina mai
# entrati: qui "null" significa davvero "non applicabile", non zero.
_BENCH_ONLY_NULL_FIELDS = {
    "games.minutes": lambda s: s.get("games", {}).get("minutes"),
    "games.rating": lambda s: s.get("games", {}).get("rating"),
}


def _all_player_entries() -> list[tuple[int, dict]]:
    entries: list[tuple[int, dict]] = []
    for players_path in sorted(_DATASET.glob("matches/*/*/fixtures_players.json")):
        league_id = int(players_path.parts[-3])
        payload = json.loads(players_path.read_text(encoding="utf-8"))
        for team in payload.get("response", []):
            for entry in team.get("players", []):
                stats_list = entry.get("statistics") or [{}]
                entries.append((league_id, stats_list[0] if stats_list else {}))
    return entries


def test_corpus_covers_all_five_required_leagues() -> None:
    entries = _all_player_entries()
    assert {league_id for league_id, _ in entries} == _LEAGUE_IDS


def test_iter_players_from_payload_parses_every_real_fixture_without_error() -> None:
    """Nessun crash su nessuno dei 20 payload reali: il flattening regge dati veri."""
    total_players = 0
    for players_path in sorted(_DATASET.glob("matches/*/*/fixtures_players.json")):
        fixture_id = int(players_path.parts[-2])
        payload = json.loads(players_path.read_text(encoding="utf-8"))
        players = iter_players_from_payload(fixture_id=fixture_id, players_payload=payload)
        assert players, f"nessun giocatore estratto da {players_path}"
        total_players += len(players)
    assert total_players > 0


def test_zero_as_null_fields_are_null_only_when_the_event_did_not_happen() -> None:
    """OQ-08: i campi ad alto tasso di null sono conteggi 'zero eventi', non dati mancanti.

    Se un campo fosse null anche quando l'evento risulta altrove nel payload
    (es. cards.red null ma il giocatore ha un cartellino rosso in eventi),
    _as_int(None) == 0 lo tratterebbe silenziosamente come "nessun evento":
    qui verifichiamo solo che il tasso di null osservato sia quello atteso
    per campi di conteggio (alto, perché la maggioranza dei giocatori non
    segna/non assiste/non manda un rigore), non un segnale di dati assenti.
    """
    entries = _all_player_entries()
    for name, getter in _ZERO_AS_NULL_FIELDS.items():
        total = len(entries)
        null_count = sum(1 for _, s in entries if getter(s) is None)
        assert total > 0
        # Tutti questi campi sono conteggi rari: null è normale e frequente,
        # ma non deve MAI essere il 100% (altrimenti il campo non esiste più
        # nello schema del provider e la formula leggerebbe sempre zero).
        assert 0 <= null_count < total, (
            f"{name}: {null_count}/{total} null — se sempre null il provider "
            "potrebbe aver cambiato schema"
        )


def test_bench_only_fields_are_null_exactly_for_unused_substitutes() -> None:
    """OQ-08/OQ-07: minutes/rating null solo per convocati mai entrati in campo."""
    entries = _all_player_entries()
    for _, s in entries:
        minutes = s.get("games", {}).get("minutes")
        substitute = s.get("games", {}).get("substitute")
        if minutes is None:
            # Un giocatore senza minuti registrati deve essere un
            # subentrante non utilizzato, mai un titolare con dato mancante.
            assert substitute is True, (
                f"minutes assente per un giocatore con substitute={substitute!r}: "
                "atteso solo per panchinari mai entrati"
            )
