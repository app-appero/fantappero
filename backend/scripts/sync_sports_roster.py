"""Sync MVP sports roster from API-Football or offline fixtures (EP04-03).

Examples (Docker Compose, from monorepo root):

  # Offline from corpus fixtures (no API key; richiede catalogo già sincronizzato)
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/sync_sports_roster.py --from-fixtures

  # Live provider (requires API_FOOTBALL_KEY in env)
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/sync_sports_roster.py --from-provider
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import database.models  # noqa: F401 — register ORM mappers
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.provider.client import build_client_from_settings
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.sync import PlayersBatch, SquadBatch, sync_roster, sync_mvp_roster_with_client

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "api_football"


def _sync_from_fixtures() -> dict[str, int]:
    squads_wolves = parse_envelope(
        json.loads((FIXTURES / "reference" / "players_squads_wolves.json").read_text(encoding="utf-8")),
        endpoint="/players/squads",
        http_status=200,
    )
    squads_chelsea = parse_envelope(
        json.loads((FIXTURES / "reference" / "players_squads_chelsea.json").read_text(encoding="utf-8")),
        endpoint="/players/squads",
        http_status=200,
    )
    players_wolves = parse_envelope(
        json.loads((FIXTURES / "reference" / "players_wolves.json").read_text(encoding="utf-8")),
        endpoint="/players",
        http_status=200,
    )
    transfers = parse_envelope(
        json.loads((FIXTURES / "reference" / "transfers_sample.json").read_text(encoding="utf-8")),
        endpoint="/transfers",
        http_status=200,
    )

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            result = sync_roster(
                session,
                squad_batches=[
                    SquadBatch(
                        envelope=squads_wolves,
                        club_provider_id=39,
                        competition_provider_id=39,
                        season_year=2026,
                    ),
                    SquadBatch(
                        envelope=squads_chelsea,
                        club_provider_id=49,
                        competition_provider_id=39,
                        season_year=2026,
                    ),
                ],
                players_batches=[
                    PlayersBatch(
                        envelope=players_wolves,
                        club_provider_id=39,
                        season_year=2026,
                    ),
                ],
                transfers_envelopes=[transfers],
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
                result = sync_mvp_roster_with_client(session, client)
    finally:
        engine.dispose()
    return _counters_dict(result.counters)


def _counters_dict(counters: object) -> dict[str, int]:
    return {
        "athletes_created": int(getattr(counters, "athletes_created")),
        "athletes_updated": int(getattr(counters, "athletes_updated")),
        "memberships_created": int(getattr(counters, "memberships_created")),
        "memberships_updated": int(getattr(counters, "memberships_updated")),
        "transfers_created": int(getattr(counters, "transfers_created")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincronizza calciatori, rose reali e trasferimenti MVP",
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
