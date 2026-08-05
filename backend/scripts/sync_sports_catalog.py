"""Sync MVP sports catalog from API-Football or offline fixtures (EP04-02).

Examples (Docker Compose, from monorepo root):

  # Offline from corpus fixtures (no API key)
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/sync_sports_catalog.py --from-fixtures

  # Live provider (requires API_FOOTBALL_KEY in env)
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/sync_sports_catalog.py --from-provider
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import database.models  # noqa: F401 — register ORM mappers
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.catalog.sync import TeamsBatch, sync_catalog, sync_mvp_catalog_with_client
from sports_data.provider.client import build_client_from_settings
from sports_data.provider.constants import MVP_LEAGUE_IDS
from sports_data.provider.envelope import parse_envelope
from sports_data.provider.mapping import map_competitions

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "api_football"


def _sync_from_fixtures() -> dict[str, int]:
    leagues_payload = json.loads(
        (FIXTURES / "reference" / "leagues.json").read_text(encoding="utf-8")
    )
    teams_payload = json.loads((FIXTURES / "reference" / "teams.json").read_text(encoding="utf-8"))
    leagues = parse_envelope(leagues_payload, endpoint="/leagues", http_status=200)
    teams = parse_envelope(teams_payload, endpoint="/teams", http_status=200)

    competitions = [
        c for c in map_competitions(leagues) if c.provider_id in MVP_LEAGUE_IDS and c.season_year
    ]
    # Offline corpus teams.json is a mixed sample: attach to first MVP competition/season.
    anchor = competitions[0]
    batches = [
        TeamsBatch(
            envelope=teams,
            competition_provider_id=anchor.provider_id,
            season_year=int(anchor.season_year),
        ),
    ]

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            result = sync_catalog(
                session,
                leagues_envelope=leagues,
                teams_batches=batches,
                store_snapshots=True,
            )
    finally:
        engine.dispose()
    return _counters_dict(result.counters)


def _sync_from_provider() -> dict[str, int]:
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with build_client_from_settings(settings) as client:
            with session_scope(factory) as session:
                result = sync_mvp_catalog_with_client(session, client)
    finally:
        engine.dispose()
    return _counters_dict(result.counters)


def _counters_dict(counters: object) -> dict[str, int]:
    return {
        "competitions_created": int(getattr(counters, "competitions_created")),
        "competitions_updated": int(getattr(counters, "competitions_updated")),
        "seasons_created": int(getattr(counters, "seasons_created")),
        "seasons_updated": int(getattr(counters, "seasons_updated")),
        "clubs_created": int(getattr(counters, "clubs_created")),
        "clubs_updated": int(getattr(counters, "clubs_updated")),
        "memberships_created": int(getattr(counters, "memberships_created")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincronizza catalogo MVP competizioni/stagioni/club"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from-fixtures",
        action="store_true",
        help="Usa payload campione in tests/fixtures/api_football (offline)",
    )
    source.add_argument(
        "--from-provider",
        action="store_true",
        help="Chiama API-Football (richiede API_FOOTBALL_KEY)",
    )
    args = parser.parse_args(argv)
    summary = _sync_from_fixtures() if args.from_fixtures else _sync_from_provider()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
