"""Avviso sulle rose prima del calendario H2H e generazione forzata (Rosario 22/11)."""

from __future__ import annotations

from uuid import uuid4

from database.enums import FantasyRole
from fantasy_teams.composition import evaluate_roster_composition, limits_from_rules
from fantasy_teams.composition_service import roster_problem_labels
from leagues.validators import CALENDAR_ROSTERS_INVALID_CODE, calendar_rosters_invalid_error

LIMITS = limits_from_rules(roster_size=35, goalkeepers=3, defenders=11, midfielders=11, forwards=10)
COMPETITIONS = [uuid4(), uuid4(), uuid4()]


def _roles(p: int, d: int, c: int, a: int) -> list[FantasyRole | None]:
    return [FantasyRole.P] * p + [FantasyRole.D] * d + [FantasyRole.C] * c + [FantasyRole.A] * a


def _labels(roles: list[FantasyRole | None], **kwargs: object) -> list[str]:
    report = evaluate_roster_composition(
        limits=LIMITS,
        roles=roles,
        competition_ids=kwargs.pop("competition_ids", COMPETITIONS),  # type: ignore[arg-type]
        require_complete=True,
        **kwargs,  # type: ignore[arg-type]
    )
    return roster_problem_labels(report)


def test_role_change_lists_the_role_over_and_the_role_under_quota() -> None:
    # Un difensore diventato attaccante: rosa a 35, ruoli fuori quota.
    assert _labels(_roles(3, 10, 11, 11)) == ["Difensori 10 su 11", "Attaccanti 11 su 10"]


def test_valid_roster_has_no_labels() -> None:
    assert _labels(_roles(3, 11, 11, 10)) == []


def test_incomplete_roster_and_competitions_are_named() -> None:
    labels = _labels(_roles(3, 11, 11, 9), competition_ids=COMPETITIONS[:2])
    assert labels == [
        "Rosa incompleta: 34 su 35",
        "Attaccanti 9 su 10",
        "Campionati rappresentati: 2 su almeno 3",
    ]


def test_unresolved_roles_are_counted() -> None:
    labels = _labels(_roles(3, 11, 11, 8), unresolved_role_count=2)
    assert labels == ["Attaccanti 8 su 10", "2 calciatori senza ruolo nel listone"]


def test_error_carries_teams_and_names_the_first_ones_in_the_message() -> None:
    teams = [
        {"teamId": str(index), "teamName": f"Squadra {index}", "issues": ["Attaccanti 11 su 10"]}
        for index in range(5)
    ]
    error = calendar_rosters_invalid_error(teams)
    assert error.code == CALENDAR_ROSTERS_INVALID_CODE
    assert error.extra == {"teams": teams}
    assert "Squadra 0: Attaccanti 11 su 10; Squadra 1" in error.message
    assert "Squadra 3" not in error.message
    assert "e altre 2 squadre" in error.message
    assert "genera comunque il calendario" in error.message
    confirm = calendar_rosters_invalid_error(teams[:1], action="conferma")
    assert "conferma comunque il calendario" in confirm.message
    assert "altre" not in confirm.message
