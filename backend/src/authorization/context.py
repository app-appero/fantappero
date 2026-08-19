"""Permission context types (EP02-03)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from auth.models.user import User
from database.enums import GlobalRole, LeagueMemberRole, LeagueRole, platform_role_to_global_role
from leagues.models.league import League


@dataclass(frozen=True, slots=True)
class ActiveLeague:
    """League context used to resolve tenant-scoped permissions."""

    id: UUID
    name: str
    role: LeagueRole


@dataclass(frozen=True, slots=True)
class LeagueAccess:
    """Resolved league access for a request (membership or operator bypass)."""

    league: League
    user: User
    membership_role: LeagueMemberRole | None
    operator_bypass: bool = False

    @property
    def api_role(self) -> LeagueRole | None:
        if self.membership_role is None:
            return None
        from database.enums import league_member_role_to_league_role

        return league_member_role_to_league_role(self.membership_role)


@dataclass(frozen=True, slots=True)
class PermissionContext:
    """Effective permission inputs for the current request."""

    user: User
    global_role: GlobalRole
    active_league: ActiveLeague | None

    @classmethod
    def for_user(
        cls,
        user: User,
        *,
        league_access: LeagueAccess | None = None,
    ) -> PermissionContext:
        active_league: ActiveLeague | None = None
        if league_access is not None and league_access.api_role is not None:
            active_league = ActiveLeague(
                id=league_access.league.id,
                name=league_access.league.name,
                role=league_access.api_role,
            )
        return cls(
            user=user,
            global_role=platform_role_to_global_role(user.platform_role),
            active_league=active_league,
        )
