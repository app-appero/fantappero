"""ORM models — import all mapped classes for Alembic autogenerate."""

from database.models.accounts import AuthSession, AuthToken, User
from database.models.competitions import Competition
from database.models.infrastructure import SystemFlag
from database.models.league_audit import LeagueAuditEvent
from database.models.leagues import League, LeagueMembership
from database.models.privacy import PrivacyAuditEvent
from database.models.profiles import UserProfile

__all__ = [
    "AuthSession",
    "AuthToken",
    "Competition",
    "League",
    "LeagueAuditEvent",
    "LeagueMembership",
    "PrivacyAuditEvent",
    "SystemFlag",
    "User",
    "UserProfile",
]
