"""Table naming conventions (ADR-0004)."""

from __future__ import annotations

from database.models.accounts import AuthSession, AuthToken, User
from database.models.infrastructure import SystemFlag
from database.models.leagues import League, LeagueMembership
from database.models.profiles import UserProfile


def test_table_names_are_plural_snake_case() -> None:
    assert User.__tablename__ == "users"
    assert AuthSession.__tablename__ == "auth_sessions"
    assert AuthToken.__tablename__ == "auth_tokens"
    assert League.__tablename__ == "leagues"
    assert LeagueMembership.__tablename__ == "league_memberships"
    assert SystemFlag.__tablename__ == "system_flags"
    assert UserProfile.__tablename__ == "user_profiles"
    from database.models.competitions import Competition
    from database.models.privacy import PrivacyAuditEvent

    assert Competition.__tablename__ == "competitions"
    assert PrivacyAuditEvent.__tablename__ == "privacy_audit_events"
    from database.models.league_audit import LeagueAuditEvent

    assert LeagueAuditEvent.__tablename__ == "league_audit_events"
