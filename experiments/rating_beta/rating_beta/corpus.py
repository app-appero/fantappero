"""Offline corpus runner — reads EP00-02 fixtures only (no DB writes)."""

from __future__ import annotations

import json
from pathlib import Path

from .config import FormulaConfig, REPO_ROOT
from .formula import RatingResult, compute_rating
from .input import iter_players_from_payload, own_goal_player_ids_from_events

DEFAULT_CORPUS = REPO_ROOT / "backend" / "tests" / "fixtures" / "api_football"


def load_corpus_ratings(
    config: FormulaConfig,
    corpus_root: Path | None = None,
    fixture_ids: set[int] | None = None,
) -> list[RatingResult]:
    root = corpus_root or DEFAULT_CORPUS
    matches = root / "matches"
    results: list[RatingResult] = []

    for players_path in sorted(matches.glob("*/*/fixtures_players.json")):
        fixture_id = int(players_path.parent.name)
        if fixture_ids is not None and fixture_id not in fixture_ids:
            continue
        league_dir = players_path.parent
        events_path = league_dir / "fixtures_events.json"
        players_payload = json.loads(players_path.read_text(encoding="utf-8"))
        own_goals: set[int] = set()
        if events_path.exists():
            events_payload = json.loads(events_path.read_text(encoding="utf-8"))
            own_goals = own_goal_player_ids_from_events(events_payload)
        for player in iter_players_from_payload(
            fixture_id=fixture_id,
            players_payload=players_payload,
            own_goal_player_ids=own_goals,
        ):
            results.append(compute_rating(player, config))
    return results
