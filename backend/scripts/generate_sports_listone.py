"""Generate official listone roles from roster memberships (EP04-04).

Examples (Docker Compose, from monorepo root):

  # After catalog + roster sync
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/generate_sports_listone.py --season-year 2026
"""

from __future__ import annotations

import argparse
import sys

import database.models  # noqa: F401 — register ORM mappers
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.listone.generate import generate_official_listone


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera il listone ufficiale P–D–C–A.")
    parser.add_argument(
        "--season-year",
        type=int,
        required=True,
        help="Anno stagione sportiva (es. 2026).",
    )
    args = parser.parse_args(argv)

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            result = generate_official_listone(session, season_year=args.season_year)
    finally:
        engine.dispose()

    c = result.counters
    print(
        f"listone season={result.season_year} mapping={result.mapping_version} "
        f"created={c.created} updated={c.updated} unchanged={c.unchanged} "
        f"skipped_unmapped={c.skipped_unmapped} deactivated={c.deactivated}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
