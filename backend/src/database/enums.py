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


class UserType(str, enum.Enum):
    """Kind of fantasy coach account."""

    HUMAN = "human"
    AI = "ai"


# Backward-compatible aliases used by auth service imports.
AuthTokenPurpose = AuthTokenType


class GlobalRole(str, enum.Enum):
    """API-facing global role (mapped from PlatformRole)."""

    MEMBER = "member"
    GLOBAL_OPERATOR = "global_operator"


def platform_role_to_global_role(role: PlatformRole) -> GlobalRole:
    if role == PlatformRole.OPERATOR:
        return GlobalRole.GLOBAL_OPERATOR
    return GlobalRole.MEMBER


class LeagueMemberRole(str, enum.Enum):
    """Role stored on ``league_memberships`` (EP02-01 schema)."""

    OWNER = "owner"
    MEMBER = "member"


class LeagueRole(str, enum.Enum):
    """API-facing league role (aligned with ``@fantappero/contracts``)."""

    MEMBER = "member"
    LEAGUE_ADMIN = "league_admin"


class LeagueState(str, enum.Enum):
    """Lifecycle state for a private league (EP03-05)."""

    DRAFT = "draft"
    CONFIGURING = "configuring"
    AUCTION = "auction"
    ACTIVE = "active"
    CONCLUDED = "concluded"
    ARCHIVED = "archived"


class FantasyRole(str, enum.Enum):
    """Official FantApperò listone roles (P–D–C–A)."""

    P = "P"
    D = "D"
    C = "C"
    A = "A"


class LeagueAuditAction(str, enum.Enum):
    """League configuration and membership audit events."""

    LEAGUE_CREATED = "league_created"
    LEAGUE_RULES_UPDATED = "league_rules_updated"
    LEAGUE_INVITE_CREATED = "league_invite_created"
    LEAGUE_INVITE_REVOKED = "league_invite_revoked"
    LEAGUE_MEMBER_JOINED = "league_member_joined"
    LEAGUE_MEMBER_REMOVED = "league_member_removed"
    LEAGUE_ADMIN_TRANSFERRED = "league_admin_transferred"
    LEAGUE_STATE_CHANGED = "league_state_changed"
    NAMED_INVITE_CREATED = "named_invite_created"
    NAMED_INVITE_ACCEPTED = "named_invite_accepted"
    NAMED_INVITE_DECLINED = "named_invite_declined"
    NAMED_INVITE_REVOKED = "named_invite_revoked"
    LEAGUE_CALENDAR_GENERATED = "league_calendar_generated"
    LEAGUE_CALENDAR_CONFIRMED = "league_calendar_confirmed"
    LEAGUE_ROLE_OVERRIDE_SET = "league_role_override_set"
    LEAGUE_ROLE_OVERRIDE_CLEARED = "league_role_override_cleared"
    LEAGUE_LISTONE_REFRESHED = "league_listone_refreshed"
    LEAGUE_DELETED = "league_deleted"


class LeagueCalendarStatus(str, enum.Enum):
    """Lifecycle of a league H2H calendar (EP03-06)."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"


class LeagueCalendarFormat(str, enum.Enum):
    """Supported H2H calendar formats for the Standard preset."""

    SINGLE_ROUND_ROBIN = "single_round_robin"


class NamedInviteStatus(str, enum.Enum):
    """Lifecycle of an invitation addressed to one user."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PrivacyAuditAction(str, enum.Enum):
    """Privacy-related audit events (EP02-04 / EP11-03)."""

    DATA_EXPORT = "data_export"
    ACCOUNT_DELETE = "account_delete"


class Permission(str, enum.Enum):
    """Fine-grained permissions mirrored from client contracts (EP02-03)."""

    LEAGUE_VIEW = "league:view"
    LEAGUE_ADMIN = "league:admin"
    ROSTER_VIEW = "roster:view"
    ROSTER_EDIT = "roster:edit"
    MARKET_VIEW = "market:view"
    MARKET_MANAGE = "market:manage"
    MATCHDAY_VIEW = "matchday:view"
    PROFILE_VIEW = "profile:view"
    GLOBAL_OPERATE = "global:operate"


def league_member_role_to_league_role(role: LeagueMemberRole) -> LeagueRole:
    if role == LeagueMemberRole.OWNER:
        return LeagueRole.LEAGUE_ADMIN
    return LeagueRole.MEMBER
