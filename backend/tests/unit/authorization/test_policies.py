"""Pure authorization policy unit tests (EP02-03)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from authorization.policies import (
    can_create_league,
    can_delete_own_account,
    can_export_own_data,
    can_mutate_user_profile,
    can_read_league,
    can_read_user_profile,
    can_update_league,
    is_platform_operator,
)
from database.enums import LeagueMemberRole, PlatformRole
from database.models.accounts import User
from database.models.leagues import LeagueMembership


def _user(*, role: PlatformRole = PlatformRole.USER, verified: bool = True) -> User:
    user = User(
        id=uuid.uuid4(),
        email="player@example.com",
        password_hash="hash",
        platform_role=role,
    )
    if verified:
        user.email_verified_at = datetime.now(UTC)
    return user


def _membership(*, user: User, role: LeagueMemberRole) -> LeagueMembership:
    return LeagueMembership(
        league_id=uuid.uuid4(),
        user_id=user.id,
        role=role,
    )


def test_platform_operator_detection() -> None:
    assert is_platform_operator(_user(role=PlatformRole.OPERATOR)) is True
    assert is_platform_operator(_user(role=PlatformRole.USER)) is False


def test_user_profile_read_self_or_operator() -> None:
    actor = _user()
    assert can_read_user_profile(actor=actor, target_user_id=actor.id) is True
    assert can_read_user_profile(actor=actor, target_user_id=uuid.uuid4()) is False

    operator = _user(role=PlatformRole.OPERATOR)
    assert can_read_user_profile(actor=operator, target_user_id=uuid.uuid4()) is True


def test_user_profile_mutate_self_only() -> None:
    actor = _user()
    assert can_mutate_user_profile(actor=actor, target_user_id=actor.id) is True
    assert can_mutate_user_profile(actor=actor, target_user_id=uuid.uuid4()) is False

    operator = _user(role=PlatformRole.OPERATOR)
    assert can_mutate_user_profile(actor=operator, target_user_id=uuid.uuid4()) is False


def test_league_read_requires_membership_or_operator() -> None:
    actor = _user()
    membership = _membership(user=actor, role=LeagueMemberRole.MEMBER)
    assert can_read_league(actor=actor, membership=membership) is True
    assert can_read_league(actor=actor, membership=None) is False

    operator = _user(role=PlatformRole.OPERATOR)
    assert can_read_league(actor=operator, membership=None) is True


def test_league_update_requires_owner_or_operator() -> None:
    actor = _user()
    owner_membership = _membership(user=actor, role=LeagueMemberRole.OWNER)
    member_membership = _membership(user=actor, role=LeagueMemberRole.MEMBER)

    assert can_update_league(actor=actor, membership=owner_membership) is True
    assert can_update_league(actor=actor, membership=member_membership) is False
    assert can_update_league(actor=actor, membership=None) is False

    operator = _user(role=PlatformRole.OPERATOR)
    assert can_update_league(actor=operator, membership=None) is True


def test_league_create_requires_verified_email() -> None:
    assert can_create_league(actor=_user(verified=True)) is True
    assert can_create_league(actor=_user(verified=False)) is False


def test_data_export_self_only() -> None:
    actor = _user()
    assert can_export_own_data(actor=actor, target_user_id=actor.id) is True
    assert can_export_own_data(actor=actor, target_user_id=uuid.uuid4()) is False

    operator = _user(role=PlatformRole.OPERATOR)
    assert can_export_own_data(actor=operator, target_user_id=uuid.uuid4()) is False


def test_account_delete_self_only() -> None:
    actor = _user()
    assert can_delete_own_account(actor=actor, target_user_id=actor.id) is True
    assert can_delete_own_account(actor=actor, target_user_id=uuid.uuid4()) is False

    operator = _user(role=PlatformRole.OPERATOR)
    assert can_delete_own_account(actor=operator, target_user_id=uuid.uuid4()) is False
