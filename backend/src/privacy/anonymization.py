"""Rules for anonymizing personal data while preserving competitive league history."""

from __future__ import annotations

import uuid

from database.models.leagues import LeagueMembership
from database.models.profiles import UserProfile

ANONYMIZED_DISPLAY_NAME = "Deleted User"
ANONYMIZED_EMAIL_DOMAIN = "anonymized.local"
EXPORT_FORMAT_VERSION = "2026-01"


def anonymized_email(user_id: uuid.UUID) -> str:
    """Deterministic tombstone email that frees the original address for re-registration."""

    return f"deleted+{user_id}@{ANONYMIZED_EMAIL_DOMAIN}"


def anonymized_historical_label(display_name: str | None) -> str:
    """Label stored on league memberships so roster history stays readable without PII."""

    if display_name and display_name.strip():
        return f"{ANONYMIZED_DISPLAY_NAME} ({display_name[:1]}.***)"
    return ANONYMIZED_DISPLAY_NAME


def scrub_profile(profile: UserProfile) -> None:
    """Remove personal profile fields; keep structural defaults for FK integrity."""

    profile.display_name = ANONYMIZED_DISPLAY_NAME
    profile.avatar_url = None
    profile.notifications_email = False
    profile.notifications_push = False


def snapshot_membership_history(
    membership: LeagueMembership,
    *,
    historical_label: str,
) -> None:
    """Preserve how the member appeared in league standings without retaining PII."""

    membership.historical_display_name = historical_label


def competitive_records_preserved(*, membership_count: int) -> dict[str, int | bool]:
    """Summary for export/audit — league memberships remain linked by user id."""

    return {
        "league_memberships_preserved": membership_count,
        "competitive_tables_present": False,
    }
