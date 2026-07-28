"""Shared helpers for database integration tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

BACKEND_ROOT = Path(__file__).resolve().parents[3]
BASELINE_REVISION = "7f3a1c9e2b04"


def database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


def require_database_url() -> str:
    url = database_url()
    if not url:
        pytest.skip("DATABASE_URL not set — skipping database integration tests")
    return url


def run_alembic(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env=merged,
    )


def reset_to_base(url: str) -> None:
    result = run_alembic("downgrade", "base", env={"DATABASE_URL": url})
    if result.returncode != 0:
        pytest.fail(f"alembic downgrade base failed:\n{result.stdout}\n{result.stderr}")


def upgrade_head(url: str) -> None:
    result = run_alembic("upgrade", "head", env={"DATABASE_URL": url})
    if result.returncode != 0:
        pytest.fail(f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}")


def alembic_check(url: str) -> subprocess.CompletedProcess[str]:
    return run_alembic("check", env={"DATABASE_URL": url})


def create_engine_for_url(url: str) -> Engine:
    from database.session import normalize_database_url

    return create_engine(normalize_database_url(url), pool_pre_ping=True)


def table_exists(engine: Engine, table_name: str) -> bool:
    return inspect(engine).has_table(table_name)


def autogenerate_has_ops(url: str) -> bool:
    """Return True when autogenerate would emit migration operations."""

    result = run_alembic(
        "revision",
        "--autogenerate",
        "-m",
        "drift_probe",
        env={"DATABASE_URL": url},
    )
    if result.returncode != 0:
        pytest.fail(f"alembic revision --autogenerate failed:\n{result.stdout}\n{result.stderr}")

    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    created = sorted(
        versions_dir.glob("*_drift_probe.py"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not created:
        return False

    probe_path = created[0]
    try:
        content = probe_path.read_text(encoding="utf-8")
        upgrade_body = content.split("def upgrade()", maxsplit=1)[1].split(
            "def downgrade()", maxsplit=1
        )[0]
        return "op." in upgrade_body
    finally:
        probe_path.unlink(missing_ok=True)
