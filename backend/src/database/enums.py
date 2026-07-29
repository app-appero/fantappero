"""PostgreSQL-backed enum types."""

from __future__ import annotations

import enum


class FlagScope(str, enum.Enum):
    """Scope for infrastructural feature flags."""

    SYSTEM = "system"
    TENANT = "tenant"


class AuthTokenType(str, enum.Enum):
    """One-time auth token purposes."""

    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class PlatformRole(str, enum.Enum):
    """Platform-wide role for a registered account."""

    USER = "user"
    OPERATOR = "operator"


class LeagueMemberRole(str, enum.Enum):
    """Membership role within a fantasy league."""

    OWNER = "owner"
    MEMBER = "member"


class PrivacyAuditAction(str, enum.Enum):
    """Audited privacy operations."""

    DATA_EXPORT = "data_export"
    ACCOUNT_DELETE = "account_delete"


class LeagueState(str, enum.Enum):
    """Lifecycle state for a fantasy league."""

    DRAFT = "draft"
    ACTIVE = "active"


class LeagueAuditAction(str, enum.Enum):
    """Audited league configuration operations."""

    LEAGUE_CREATED = "league_created"
