#!/usr/bin/env python3
"""Migration coherence check for CI / local gates (EP01-03).

Until Alembic lands (EP01-06), the expected state is: no migration tree.
This script:

- exits 0 when no migration tooling is present (legacy pre-EP01-06);
- exits 1 if orphaned / incoherent migration artifacts appear;
- when Alembic is present, validates layout, single head, and runs
  ``alembic check`` (requires ``DATABASE_URL`` for drift detection).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

ALEMBIC_INI = BACKEND / "alembic.ini"
ALEMBIC_DIR = BACKEND / "alembic"
VERSIONS_DIR = ALEMBIC_DIR / "versions"
MIGRATIONS_DIR = BACKEND / "migrations"


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _ok(message: str) -> int:
    print(f"OK: {message}")
    return 0


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        check=False,
        text=True,
        capture_output=True,
    )


def main() -> int:
    has_ini = ALEMBIC_INI.is_file()
    has_alembic = ALEMBIC_DIR.is_dir()
    has_migrations = MIGRATIONS_DIR.is_dir()

    if not has_ini and not has_alembic and not has_migrations:
        return _ok("no migration tree yet (deferred to EP01-06)")

    if has_migrations and not (has_ini or has_alembic):
        return _fail(
            "backend/migrations/ exists without alembic.ini / alembic/ "
            "(incoherent until EP01-06 defines the layout)"
        )

    if has_ini != has_alembic:
        return _fail("alembic.ini and alembic/ must both exist together")

    assert has_ini and has_alembic  # for type checkers

    if not VERSIONS_DIR.is_dir():
        return _fail("alembic/versions/ is missing")

    version_files = sorted(VERSIONS_DIR.glob("*.py"))
    version_files = [p for p in version_files if p.name != "__init__.py"]
    print(f"Found {len(version_files)} Alembic revision file(s).")

    if shutil.which("alembic") is None:
        # Prefer `python -m alembic` once the package is a backend dependency.
        probe = _run_alembic("--help")
        if probe.returncode != 0:
            return _ok(
                "Alembic layout present; alembic package not installed — "
                "layout-only check passed (install Alembic in EP01-06)"
            )

    heads = _run_alembic("heads")
    if heads.returncode != 0:
        print(heads.stdout)
        print(heads.stderr, file=sys.stderr)
        return _fail("alembic heads failed")

    head_lines = [line for line in heads.stdout.splitlines() if line.strip()]
    print(heads.stdout.rstrip())
    if len(head_lines) > 1:
        return _fail("multiple Alembic heads detected — rebase/merge revisions")

    if not os.environ.get("DATABASE_URL", "").strip():
        return _ok(
            "Alembic layout coherent (single head; set DATABASE_URL for drift check)"
        )

    check = _run_alembic("check")
    if check.returncode != 0:
        print(check.stdout)
        print(check.stderr, file=sys.stderr)
        return _fail("alembic check failed — schema drift or DATABASE_URL mismatch")

    return _ok("Alembic layout coherent (single head + check)")


if __name__ == "__main__":
    raise SystemExit(main())
