"""Competitive-record anonymization rules (EP02-04)."""

from __future__ import annotations

import uuid

from database.models.leagues import LeagueMembership
from database.models.profiles import UserProfile
from privacy.anonymization import (
    ANONYMIZED_DISPLAY_NAME,
    anonymized_email,
    anonymized_historical_label,
    competitive_records_preserved,
    scrub_profile,
    snapshot_membership_history,
)


def test_anonymized_email_is_deterministic_tombstone() -> None:
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
    expected = "deleted+00000000-0000-0000-0000-000000000099@anonymized.local"
    assert anonymized_email(user_id) == expected


def test_historical_label_masks_display_name() -> None:
    assert anonymized_historical_label("Mario Rossi") == "Deleted User (M.***)"
    assert anonymized_historical_label(None) == ANONYMIZED_DISPLAY_NAME


def test_scrub_profile_removes_personal_fields() -> None:
    profile = UserProfile(user_id=uuid.uuid4(), display_name="Mario", avatar_url="data:image/png")
    scrub_profile(profile)
    assert profile.display_name == ANONYMIZED_DISPLAY_NAME
    assert profile.avatar_url is None
    assert profile.notifications_email is False
    assert profile.notifications_push is False


def test_membership_snapshot_preserves_league_history() -> None:
    membership = LeagueMembership(
        league_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )
    snapshot_membership_history(membership, historical_label="Deleted User (M.***)")
    assert membership.historical_display_name == "Deleted User (M.***)"


def test_competitive_summary_reports_preserved_memberships() -> None:
    summary = competitive_records_preserved(membership_count=2)
    assert summary["league_memberships_preserved"] == 2
    assert summary["competitive_tables_present"] is False
