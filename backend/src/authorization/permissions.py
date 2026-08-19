"""Permission matrix mirrored from ``@fantappero/contracts`` (EP02-03)."""

from __future__ import annotations

from authorization.context import PermissionContext
from database.enums import GlobalRole, LeagueRole, Permission

GLOBAL_OPERATOR_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.LEAGUE_VIEW,
        Permission.LEAGUE_ADMIN,
        Permission.ROSTER_VIEW,
        Permission.ROSTER_EDIT,
        Permission.MARKET_VIEW,
        Permission.MARKET_MANAGE,
        Permission.MATCHDAY_VIEW,
        Permission.PROFILE_VIEW,
        Permission.GLOBAL_OPERATE,
    }
)

LEAGUE_ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.LEAGUE_VIEW,
        Permission.LEAGUE_ADMIN,
        Permission.ROSTER_VIEW,
        Permission.ROSTER_EDIT,
        Permission.MARKET_VIEW,
        Permission.MARKET_MANAGE,
        Permission.MATCHDAY_VIEW,
        Permission.PROFILE_VIEW,
    }
)

LEAGUE_MEMBER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.LEAGUE_VIEW,
        Permission.ROSTER_VIEW,
        Permission.ROSTER_EDIT,
        Permission.MARKET_VIEW,
        Permission.MATCHDAY_VIEW,
        Permission.PROFILE_VIEW,
    }
)


def resolve_permissions(context: PermissionContext) -> set[Permission]:
    """Resolve effective permissions from session and optional league context."""
    if context.global_role == GlobalRole.GLOBAL_OPERATOR:
        return set(GLOBAL_OPERATOR_PERMISSIONS)

    league_role = context.active_league.role if context.active_league is not None else None
    if league_role == LeagueRole.LEAGUE_ADMIN:
        base = LEAGUE_ADMIN_PERMISSIONS
    else:
        base = LEAGUE_MEMBER_PERMISSIONS
    return set(base)


def has_permissions(context: PermissionContext, required: tuple[Permission, ...]) -> bool:
    if not required:
        return True
    granted = resolve_permissions(context)
    return all(permission in granted for permission in required)


def has_any_permission(context: PermissionContext, required: tuple[Permission, ...]) -> bool:
    if not required:
        return True
    granted = resolve_permissions(context)
    return any(permission in granted for permission in required)
