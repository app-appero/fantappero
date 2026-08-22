"""Compare a restored database with its source without mutating either one.

The DR drill uses this after ``pg_restore``.  It compares every public table by
row count and a canonical aggregate digest, verifies sequence positions and
checks that PostgreSQL considers every public constraint validated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text

from database.session import normalize_database_url


@dataclass(frozen=True)
class TableFingerprint:
    rows: int
    digest: str


def _engine(url: str) -> Engine:
    return create_engine(normalize_database_url(url), pool_pre_ping=True, future=True)


def _public_tables(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                    """
                )
            ).scalars()
        )


def _table_fingerprint(engine: Engine, table_name: str) -> TableFingerprint:
    quoted = engine.dialect.identifier_preparer.quote(table_name)
    statement = text(
        f"""
        SELECT
            count(*)::bigint,
            md5(
                COALESCE(
                    string_agg(row_digest, '' ORDER BY row_digest),
                    ''
                )
            )
        FROM (
            SELECT md5(row_to_json(row_value)::text) AS row_digest
            FROM {quoted} AS row_value
        ) AS fingerprints
        """
    )
    with engine.connect() as connection:
        row = connection.execute(statement).one()
    return TableFingerprint(rows=int(row[0]), digest=str(row[1]))


def _sequence_fingerprint(engine: Engine) -> str:
    with engine.connect() as connection:
        sequence_names = list(
            connection.execute(
                text(
                    """
                    SELECT c.relname
                    FROM pg_class AS c
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relkind = 'S'
                    ORDER BY c.relname
                    """
                )
            ).scalars()
        )
        rows: list[tuple[str, int, bool]] = []
        for sequence_name in sequence_names:
            quoted = engine.dialect.identifier_preparer.quote(sequence_name)
            last_value, is_called = connection.execute(
                text(f"SELECT last_value, is_called FROM {quoted}")
            ).one()
            rows.append((str(sequence_name), int(last_value), bool(is_called)))
    canonical = json.dumps(rows, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _invalid_constraint_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(
                text(
                    """
                    SELECT count(*)
                    FROM pg_constraint
                    WHERE connamespace = 'public'::regnamespace AND NOT convalidated
                    """
                )
            ).scalar_one()
        )


def verify(source: Engine, restored: Engine, *, minimum_rows: int) -> dict[str, object]:
    source_tables = _public_tables(source)
    restored_tables = _public_tables(restored)
    if source_tables != restored_tables:
        missing = sorted(set(source_tables) - set(restored_tables))
        unexpected = sorted(set(restored_tables) - set(source_tables))
        raise RuntimeError(f"schema mismatch: missing={missing}, unexpected={unexpected}")

    mismatches: list[str] = []
    total_rows = 0
    key_counts: dict[str, int] = {}
    key_tables = {
        "users",
        "leagues",
        "fantasy_teams",
        "credit_ledger_entries",
        "lineup_submissions",
    }
    for table_name in source_tables:
        source_fingerprint = _table_fingerprint(source, table_name)
        restored_fingerprint = _table_fingerprint(restored, table_name)
        total_rows += source_fingerprint.rows
        if table_name in key_tables:
            key_counts[table_name] = source_fingerprint.rows
        if source_fingerprint != restored_fingerprint:
            mismatches.append(table_name)

    if mismatches:
        raise RuntimeError(f"data fingerprint mismatch in tables: {', '.join(mismatches)}")
    if total_rows < minimum_rows:
        raise RuntimeError(
            f"source dataset too small for DR evidence: rows={total_rows}, minimum={minimum_rows}"
        )

    source_sequences = _sequence_fingerprint(source)
    restored_sequences = _sequence_fingerprint(restored)
    if source_sequences != restored_sequences:
        raise RuntimeError("sequence fingerprint mismatch")

    invalid_constraints = _invalid_constraint_count(restored)
    if invalid_constraints:
        raise RuntimeError(f"restored database has {invalid_constraints} unvalidated constraints")

    return {
        "status": "ok",
        "table_count": len(source_tables),
        "total_rows": total_rows,
        "key_table_rows": dict(sorted(key_counts.items())),
        "data_fingerprints_match": True,
        "sequence_fingerprint_match": True,
        "invalid_constraints": invalid_constraints,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a FantApperò PostgreSQL restore.")
    parser.add_argument(
        "--source-url",
        default=os.environ.get("SOURCE_DATABASE_URL"),
        help="Source DATABASE_URL (or SOURCE_DATABASE_URL).",
    )
    parser.add_argument(
        "--restored-url",
        default=os.environ.get("RESTORED_DATABASE_URL") or os.environ.get("DATABASE_URL"),
        help="Restored DATABASE_URL (RESTORED_DATABASE_URL or DATABASE_URL).",
    )
    parser.add_argument("--minimum-rows", type=int, default=1)
    args = parser.parse_args()
    if not args.source_url or not args.restored_url:
        parser.error("--source-url and --restored-url are required")
    if args.minimum_rows < 0:
        parser.error("--minimum-rows must be >= 0")

    source = _engine(args.source_url)
    restored = _engine(args.restored_url)
    try:
        report = verify(source, restored, minimum_rows=args.minimum_rows)
    finally:
        source.dispose()
        restored.dispose()
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
