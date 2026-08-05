"""League validation unit tests (EP03-01)."""

from __future__ import annotations

from uuid import UUID

import pytest

from auth.exceptions import ValidationAuthError
from database.enums import LeagueMemberRole, LeagueState
from leagues.validators import (
    auction_activation_blockers,
    configuration_blockers,
    normalize_invite_code,
    validate_admin_transfer_target,
    validate_competition_ids,
    validate_configurable_league_state,
    validate_invite_credential,
    validate_invite_expiry_days,
    validate_league_name,
    validate_league_transition,
    validate_member_removal,
    validate_participant_count,
    validate_preset_name,
    validate_season_year,
    validate_standard_roster,
    validate_total_credits,
)


def test_validate_league_name_trims() -> None:
    assert validate_league_name("  Lega Test  ") == "Lega Test"


def test_validate_league_name_rejects_empty() -> None:
    with pytest.raises(ValidationAuthError, match="nome per la lega"):
        validate_league_name("   ")


def test_validate_season_year_accepts_current_window() -> None:
    assert validate_season_year(2026) == 2026


def test_validate_season_year_rejects_out_of_range() -> None:
    with pytest.raises(ValidationAuthError, match="stagione valida"):
        validate_season_year(2010)


def test_validate_competition_ids_requires_minimum() -> None:
    ids = [
        UUID("00000000-0000-4000-8000-000000000001"),
        UUID("00000000-0000-4000-8000-000000000002"),
    ]
    with pytest.raises(ValidationAuthError, match="almeno 3"):
        validate_competition_ids(ids)


def test_validate_competition_ids_rejects_duplicates() -> None:
    duplicate = UUID("00000000-0000-4000-8000-000000000001")
    ids = [duplicate, duplicate, UUID("00000000-0000-4000-8000-000000000002")]
    with pytest.raises(ValidationAuthError, match="una sola volta"):
        validate_competition_ids(ids)


def test_validate_competition_ids_accepts_three_unique() -> None:
    ids = [
        UUID("00000000-0000-4000-8000-000000000001"),
        UUID("00000000-0000-4000-8000-000000000002"),
        UUID("00000000-0000-4000-8000-000000000003"),
    ]
    assert validate_competition_ids(ids) == ids


def test_validate_preset_name_accepts_standard() -> None:
    assert validate_preset_name("Standard") == "standard"


def test_validate_preset_name_rejects_unknown() -> None:
    with pytest.raises(ValidationAuthError, match="solo il preset Standard"):
        validate_preset_name("custom")


def test_validate_participant_count_rejects_outside_range() -> None:
    with pytest.raises(ValidationAuthError, match="tra 4 e 10"):
        validate_participant_count(3)


def test_validate_total_credits_requires_positive() -> None:
    with pytest.raises(ValidationAuthError, match="maggiori di zero"):
        validate_total_credits(0)


def test_validate_standard_roster_rejects_wrong_distribution() -> None:
    with pytest.raises(ValidationAuthError, match="3P-11D-11C-10A"):
        validate_standard_roster(
            roster_size=35,
            goalkeepers=4,
            defenders=10,
            midfielders=11,
            forwards=10,
        )


@pytest.mark.parametrize("days", [1, 7, 30])
def test_validate_invite_expiry_accepts_supported_range(days: int) -> None:
    assert validate_invite_expiry_days(days) == days


@pytest.mark.parametrize("days", [0, 31])
def test_validate_invite_expiry_rejects_unsupported_range(days: int) -> None:
    with pytest.raises(ValidationAuthError) as error:
        validate_invite_expiry_days(days)
    assert error.value.code == "invalid_invite_expiry"


def test_normalize_invite_code_is_case_and_separator_insensitive() -> None:
    assert normalize_invite_code("abcde-fghij") == "ABCDEFGHIJ"


def test_validate_invite_credential_requires_exactly_one_value() -> None:
    with pytest.raises(ValidationAuthError) as missing:
        validate_invite_credential(token=None, code=None)
    with pytest.raises(ValidationAuthError) as ambiguous:
        validate_invite_credential(token="token", code="ABCDE-FGHIJ")
    assert missing.value.code == "invalid_invite"
    assert ambiguous.value.code == "invalid_invite"


def test_member_removal_rejects_league_admin() -> None:
    with pytest.raises(ValidationAuthError) as error:
        validate_member_removal(LeagueMemberRole.OWNER)
    assert error.value.code == "cannot_remove_admin"


def test_member_removal_accepts_participant() -> None:
    validate_member_removal(LeagueMemberRole.MEMBER)


def test_admin_transfer_requires_participant_target() -> None:
    with pytest.raises(ValidationAuthError) as error:
        validate_admin_transfer_target(LeagueMemberRole.OWNER)
    assert error.value.code == "invalid_transfer_target"


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (LeagueState.DRAFT, LeagueState.CONFIGURING),
        (LeagueState.CONFIGURING, LeagueState.AUCTION),
        (LeagueState.AUCTION, LeagueState.CONFIGURING),
        (LeagueState.AUCTION, LeagueState.ACTIVE),
        (LeagueState.ACTIVE, LeagueState.CONCLUDED),
        (LeagueState.CONCLUDED, LeagueState.ARCHIVED),
    ],
)
def test_lifecycle_accepts_transition_matrix(
    current: LeagueState,
    target: LeagueState,
) -> None:
    assert validate_league_transition(current, target) is True


def test_lifecycle_same_state_is_idempotent() -> None:
    assert validate_league_transition(LeagueState.CONFIGURING, LeagueState.CONFIGURING) is False


def test_lifecycle_rejects_state_jump() -> None:
    with pytest.raises(ValidationAuthError) as error:
        validate_league_transition(LeagueState.DRAFT, LeagueState.AUCTION)
    assert error.value.code == "invalid_league_transition"


@pytest.mark.parametrize("state", [LeagueState.DRAFT, LeagueState.CONFIGURING])
def test_configuration_changes_are_allowed_before_auction(state: LeagueState) -> None:
    validate_configurable_league_state(state, subject="il regolamento")


def test_configuration_changes_keep_legacy_error_code_after_auction() -> None:
    with pytest.raises(ValidationAuthError) as error:
        validate_configurable_league_state(LeagueState.AUCTION, subject="il regolamento")
    assert error.value.code == "league_not_draft"


def test_configuration_blockers_report_all_missing_requirements() -> None:
    blockers = configuration_blockers(
        rules_valid=False,
        competition_count=2,
        membership_count=2,
        participant_count=4,
        owner_count=0,
    )
    assert {blocker.code for blocker in blockers} == {
        "rules_invalid",
        "insufficient_competitions",
        "participant_count_mismatch",
        "league_admin_required",
    }


def test_auction_activation_blockers_include_calendar_until_configured() -> None:
    assert {blocker.code for blocker in auction_activation_blockers()} == {
        "calendar_not_configured",
        "fantasy_teams_not_configured",
        "credits_not_configured",
    }
    assert {blocker.code for blocker in auction_activation_blockers(calendar_configured=True)} == {
        "fantasy_teams_not_configured",
        "credits_not_configured",
    }
