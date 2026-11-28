"""Singolare/plurale dei conteggi nei blocchi di avvio stagione (QA 28/11, N1)."""

from __future__ import annotations

import pytest

from fantasy_teams.composition_service import (
    invalid_credits_label,
    invalid_rosters_label,
    missing_teams_label,
)


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1 squadra mancante"), (2, "2 squadre mancanti"), (11, "11 squadre mancanti")],
)
def test_missing_teams_label(count: int, expected: str) -> None:
    assert missing_teams_label(count) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "1 rosa non valida o incompleta"),
        (2, "2 rose non valide o incomplete"),
        (8, "8 rose non valide o incomplete"),
    ],
)
def test_invalid_rosters_label(count: int, expected: str) -> None:
    assert invalid_rosters_label(count) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "1 conto assente o non valido"),
        (3, "3 conti assenti o non validi"),
    ],
)
def test_invalid_credits_label(count: int, expected: str) -> None:
    assert invalid_credits_label(count) == expected
