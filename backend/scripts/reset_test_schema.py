"""Drop and recreate the public schema for the configured DATABASE_URL."""

from __future__ import annotations

import os
import sys

from sqlalchemy import text

from database.session import create_engine_from_url, normalize_database_url


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url or not url.rstrip("/").endswith("_test"):
        print("Refusing to reset a non-test DATABASE_URL.", file=sys.stderr)
        return 2
    engine = create_engine_from_url(normalize_database_url(url))
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        print("test schema reset")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
