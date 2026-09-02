"""Unit tests for roster validation rules (EP04-03)."""

from __future__ import annotations

from sports_data.roster.validators import (
    build_transfer_provider_key,
    transfer_requires_admin_review,
)


def test_transfer_requires_admin_review_for_loan_and_na() -> None:
    assert transfer_requires_admin_review("Loan") is True
    assert transfer_requires_admin_review("N/A") is True
    assert transfer_requires_admin_review("") is True
    assert transfer_requires_admin_review("Free") is False
    assert transfer_requires_admin_review("€ 50M") is False


def test_build_transfer_provider_key_is_stable() -> None:
    key_a = build_transfer_provider_key(
        athlete_provider_id=2887,
        transfer_date="2026-01-10",
        from_club_provider_id=39,
        to_club_provider_id=49,
        transfer_type="Free",
    )
    key_b = build_transfer_provider_key(
        athlete_provider_id=2887,
        transfer_date="2026-01-10",
        from_club_provider_id=39,
        to_club_provider_id=49,
        transfer_type="Free",
    )
    assert key_a == key_b
    assert key_a == "2887:2026-01-10:39:49:Free"
