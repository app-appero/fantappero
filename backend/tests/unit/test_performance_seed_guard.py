"""Safety contract for the disposable EP12-03 dataset."""

from __future__ import annotations

import pytest

from config.settings.base import FantapperoEnv
from devtools.seed_performance_scenario import (
    CONFIRMATION_VALUE,
    _guard_isolated_target,
)


def test_performance_seed_accepts_only_explicit_isolated_target(monkeypatch) -> None:
    monkeypatch.setenv("PERFORMANCE_SEED_CONFIRM", CONFIRMATION_VALUE)

    _guard_isolated_target(
        "postgresql://user:password@postgres-perf:5432/fantappero_performance",
        FantapperoEnv.DEVELOPMENT,
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:password@postgres:5432/fantappero_performance",
        "postgresql://user:password@postgres-perf:5432/fantappero",
    ],
)
def test_performance_seed_rejects_non_isolated_database(monkeypatch, database_url: str) -> None:
    monkeypatch.setenv("PERFORMANCE_SEED_CONFIRM", CONFIRMATION_VALUE)

    with pytest.raises(SystemExit, match="Refusing unsafe performance target"):
        _guard_isolated_target(database_url, FantapperoEnv.DEVELOPMENT)


def test_performance_seed_rejects_production_even_with_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("PERFORMANCE_SEED_CONFIRM", CONFIRMATION_VALUE)

    with pytest.raises(SystemExit, match="production"):
        _guard_isolated_target(
            "postgresql://user:password@postgres-perf:5432/fantappero_performance",
            FantapperoEnv.PRODUCTION,
        )


def test_performance_seed_requires_confirmation(monkeypatch) -> None:
    monkeypatch.delenv("PERFORMANCE_SEED_CONFIRM", raising=False)

    with pytest.raises(SystemExit, match="PERFORMANCE_SEED_CONFIRM"):
        _guard_isolated_target(
            "postgresql://user:password@postgres-perf:5432/fantappero_performance",
            FantapperoEnv.DEVELOPMENT,
        )
