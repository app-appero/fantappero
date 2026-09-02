"""Unit tests for roster composition rules (EP05-05)."""

from __future__ import annotations

from uuid import uuid4

from database.enums import FantasyRole, RosterCompositionStatus
from fantasy_teams.composition import (
    evaluate_roster_composition,
    limits_from_rules,
    would_exceed_role_quota,
)

STANDARD = limits_from_rules(
    roster_size=35,
    goalkeepers=3,
    defenders=11,
    midfielders=11,
    forwards=10,
)


def test_incomplete_roster_allowed_during_auction() -> None:
    roles = [FantasyRole.P, FantasyRole.D]
    report = evaluate_roster_composition(
        limits=STANDARD,
        roles=roles,
        competition_ids={uuid4()},
        require_complete=False,
    )
    assert report.status == RosterCompositionStatus.INCOMPLETE
    assert report.issues == ()


def test_over_quota_rejected_even_when_incomplete_allowed() -> None:
    roles = [FantasyRole.P, FantasyRole.P, FantasyRole.P, FantasyRole.P]
    report = evaluate_roster_composition(
        limits=STANDARD,
        roles=roles,
        competition_ids={uuid4(), uuid4(), uuid4()},
        require_complete=False,
    )
    assert report.status == RosterCompositionStatus.INVALID
    assert any(issue.code == "role_quota_exceeded" for issue in report.issues)


def test_season_start_requires_exact_composition_and_competitions() -> None:
    roles = (
        [FantasyRole.P] * 3
        + [FantasyRole.D] * 11
        + [FantasyRole.C] * 11
        + [FantasyRole.A] * 10
    )
    report = evaluate_roster_composition(
        limits=STANDARD,
        roles=roles,
        competition_ids={uuid4(), uuid4()},
        require_complete=True,
    )
    assert report.status == RosterCompositionStatus.INVALID
    assert any(issue.code == "insufficient_roster_competitions" for issue in report.issues)

    report_ok = evaluate_roster_composition(
        limits=STANDARD,
        roles=roles,
        competition_ids={uuid4(), uuid4(), uuid4()},
        require_complete=True,
    )
    assert report_ok.status == RosterCompositionStatus.VALIDATED
    assert report_ok.is_valid_for_season_start


def test_season_start_aggregates_all_issues() -> None:
    report = evaluate_roster_composition(
        limits=STANDARD,
        roles=[FantasyRole.P] * 4,
        competition_ids={uuid4()},
        require_complete=True,
        unresolved_role_count=1,
    )
    codes = {issue.code for issue in report.issues}
    assert "role_quota_exceeded" in codes
    assert "roster_incomplete" in codes
    assert "role_unresolved" in codes
    assert "insufficient_roster_competitions" in codes
    assert "role_quota_underfilled" in codes


def test_would_exceed_role_quota_accounts_for_replacement() -> None:
    current = [FantasyRole.P, FantasyRole.P, FantasyRole.P]
    assert would_exceed_role_quota(
        limits=STANDARD,
        current_roles=current,
        new_role=FantasyRole.P,
        replacing_role=None,
    )
    assert not would_exceed_role_quota(
        limits=STANDARD,
        current_roles=current,
        new_role=FantasyRole.P,
        replacing_role=FantasyRole.P,
    )


def test_limits_are_taken_from_configuration_not_hardcoded_call_site() -> None:
    custom = limits_from_rules(
        roster_size=4,
        goalkeepers=1,
        defenders=1,
        midfielders=1,
        forwards=1,
    )
    report = evaluate_roster_composition(
        limits=custom,
        roles=[FantasyRole.P, FantasyRole.D, FantasyRole.C, FantasyRole.A],
        competition_ids={uuid4(), uuid4(), uuid4()},
        require_complete=True,
    )
    assert report.status == RosterCompositionStatus.VALIDATED
    assert report.limits.goalkeepers == 1
