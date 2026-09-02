"""Unit tests for authorization permission matrix (EP02-03)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from auth.models.user import User
from authorization.context import ActiveLeague, PermissionContext
from authorization.permissions import has_permissions, resolve_permissions
from database.enums import GlobalRole, LeagueRole, Permission, PlatformRole


def _user(*, platform_role: PlatformRole = PlatformRole.USER) -> User:
    user = User(
        id=uuid4(),
        email="test@example.com",
        password_hash="hash",
        platform_role=platform_role,
    )
    return user


def _context(
    *,
    platform_role: PlatformRole = PlatformRole.USER,
    league_role: LeagueRole | None = LeagueRole.MEMBER,
) -> PermissionContext:
    user = _user(platform_role=platform_role)
    active_league = None
    if league_role is not None:
        active_league = ActiveLeague(id=uuid4(), name="Lega Demo", role=league_role)
    return PermissionContext(
        user=user,
        global_role=GlobalRole.GLOBAL_OPERATOR
        if platform_role == PlatformRole.OPERATOR
        else GlobalRole.MEMBER,
        active_league=active_league,
    )


@pytest.mark.parametrize(
    ("league_role", "expected"),
    [
        (LeagueRole.LEAGUE_ADMIN, True),
        (LeagueRole.MEMBER, False),
    ],
)
def test_market_manage_only_for_league_admin(league_role: LeagueRole, expected: bool) -> None:
    context = _context(league_role=league_role)
    assert (Permission.MARKET_MANAGE in resolve_permissions(context)) is expected


def test_global_operate_only_for_platform_operator() -> None:
    operator = _context(platform_role=PlatformRole.OPERATOR, league_role=None)
    member = _context(league_role=LeagueRole.MEMBER)
    admin = _context(league_role=LeagueRole.LEAGUE_ADMIN)

    assert Permission.GLOBAL_OPERATE in resolve_permissions(operator)
    assert Permission.GLOBAL_OPERATE not in resolve_permissions(member)
    assert Permission.GLOBAL_OPERATE not in resolve_permissions(admin)


def test_profile_view_for_authenticated_league_contexts() -> None:
    member = _context(league_role=LeagueRole.MEMBER)
    assert Permission.PROFILE_VIEW in resolve_permissions(member)


def test_member_without_league_gets_default_member_permissions() -> None:
    context = _context(league_role=None)
    perms = resolve_permissions(context)
    assert Permission.PROFILE_VIEW in perms
    assert Permission.LEAGUE_VIEW in perms
    assert Permission.MARKET_MANAGE not in perms


def test_has_permissions_requires_all() -> None:
    member = _context(league_role=LeagueRole.MEMBER)
    admin = _context(league_role=LeagueRole.LEAGUE_ADMIN)

    assert has_permissions(member, (Permission.MARKET_VIEW, Permission.MARKET_MANAGE)) is False
    assert has_permissions(admin, (Permission.MARKET_VIEW, Permission.MARKET_MANAGE)) is True


def test_has_permissions_empty_requirement() -> None:
    member = _context(league_role=LeagueRole.MEMBER)
    assert has_permissions(member, ()) is True
