"""Sync MVP sports fixtures from API-Football or offline corpus (EP04-05).

Examples (Docker Compose, from monorepo root):

  # Offline from corpus fixtures (no API key; richiede catalogo già sincronizzato)
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/sync_sports_fixtures.py --from-fixtures

  # Live provider (requires API_FOOTBALL_KEY in env)
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/sync_sports_fixtures.py --from-provider
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import database.models  # noqa: F401 — register ORM mappers
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.fixtures.sync import (
    FixtureDetailBatch,
    sync_fixtures,
    sync_mvp_fixtures_with_client,
)
from sports_data.provider.client import build_client_from_settings
from sports_data.provider.envelope import parse_envelope

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "api_football"
SAMPLE_MATCH = FIXTURES / "matches" / "39" / "1035055"


def _sync_from_fixtures() -> dict[str, int]:
    fixtures_env = parse_envelope(
        json.loads((SAMPLE_MATCH / "fixtures.json").read_text(encoding="utf-8")),
        endpoint="/fixtures",
        http_status=200,
    )
    events_env = parse_envelope(
        json.loads((SAMPLE_MATCH / "fixtures_events.json").read_text(encoding="utf-8")),
        endpoint="/fixtures/events",
        http_status=200,
    )
    lineups_env = parse_envelope(
        json.loads((SAMPLE_MATCH / "fixtures_lineups.json").read_text(encoding="utf-8")),
        endpoint="/fixtures/lineups",
        http_status=200,
    )
    players_env = parse_envelope(
        json.loads((SAMPLE_MATCH / "fixtures_players.json").read_text(encoding="utf-8")),
        endpoint="/fixtures/players",
        http_status=200,
    )

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            result = sync_fixtures(
                session,
                fixtures_envelopes=[fixtures_env],
                detail_batches=[
                    FixtureDetailBatch(
                        fixture_provider_id=1035055,
                        events_envelope=events_env,
                        lineups_envelope=lineups_env,
                        players_envelope=players_env,
                    ),
                ],
            )
    finally:
        engine.dispose()
    c = result.counters
    return {
        "fixtures_created": c.fixtures_created,
        "fixtures_updated": c.fixtures_updated,
        "events_created": c.events_created,
        "events_corrected": c.events_corrected,
        "lineups_created": c.lineups_created,
        "stats_created": c.stats_created,
    }


def _sync_from_provider(*, include_details: bool, max_fixtures: int | None) -> dict[str, int]:
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with build_client_from_settings(settings) as client:
            with session_scope(factory) as session:
                result = sync_mvp_fixtures_with_client(
                    session,
                    client,
                    include_details=include_details,
                    max_fixtures_per_league=max_fixtures,
                )
    finally:
        engine.dispose()
    c = result.counters
    return {
        "fixtures_created": c.fixtures_created,
        "fixtures_updated": c.fixtures_updated,
        "events_created": c.events_created,
        "events_corrected": c.events_corrected,
        "lineups_created": c.lineups_created,
        "stats_created": c.stats_created,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync sports fixtures (EP04-05)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-fixtures", action="store_true", help="Offline corpus sample match")
    source.add_argument("--from-provider", action="store_true", help="Live API-Football")
    parser.add_argument(
        "--calendar-only",
        action="store_true",
        help="With --from-provider: skip events/lineups/players",
    )
    parser.add_argument(
        "--max-fixtures-per-league",
        type=int,
        default=None,
        help="Cap detail fetches per league (live mode)",
    )
    args = parser.parse_args(argv)

    if args.from_fixtures:
        summary = _sync_from_fixtures()
    else:
        summary = _sync_from_provider(
            include_details=not args.calendar_only,
            max_fixtures=args.max_fixtures_per_league,
        )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
