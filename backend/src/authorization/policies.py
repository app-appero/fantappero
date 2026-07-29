"""Pure authorization rules for users, leagues, and platform operators."""

from __future__ import annotations

import uuid

from database.enums import LeagueMemberRole, PlatformRole
from database.models.accounts import User
from database.models.leagues import LeagueMembership


def is_platform_operator(user: User) -> bool:
    return user.platform_role == PlatformRole.OPERATOR


def can_read_user_profile(*, actor: User, target_user_id: uuid.UUID) -> bool:
    """User profiles are private; operators may read any profile for support."""

    if is_platform_operator(actor):
        return True
    return actor.id == target_user_id


def can_mutate_user_profile(*, actor: User, target_user_id: uuid.UUID) -> bool:
    """Profile updates remain self-only; operators cannot mutate user data."""

    return actor.id == target_user_id


def can_read_league(*, actor: User, membership: LeagueMembership | None) -> bool:
    """League detail requires membership unless the actor is a platform operator."""

    if is_platform_operator(actor):
        return True
    return membership is not None


def can_update_league(*, actor: User, membership: LeagueMembership | None) -> bool:
    """League updates require league owner (admin) or platform operator."""

    if is_platform_operator(actor):
        return True
    return membership is not None and membership.role == LeagueMemberRole.OWNER


def can_create_league(*, actor: User) -> bool:
    """League creation requires a verified email address."""

    return actor.email_verified_at is not None


def can_export_own_data(*, actor: User, target_user_id: uuid.UUID) -> bool:
    """Data export is a personal right — self only, not even operators."""

    return actor.id == target_user_id


def can_delete_own_account(*, actor: User, target_user_id: uuid.UUID) -> bool:
    """Account deletion is self-only; operators cannot delete on behalf of users."""

    return actor.id == target_user_id
