"""Authorization lookups and policy enforcement."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.errors import EmailNotVerifiedError, ForbiddenError, NotFoundError
from authorization.policies import (
    can_create_league,
    can_delete_own_account,
    can_export_own_data,
    can_mutate_user_profile,
    can_read_league,
    can_read_user_profile,
    can_update_league,
)
from database.models.accounts import User
from database.models.leagues import League, LeagueMembership


class AuthorizationService:
    """Enforces resource policies using membership and platform role context."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def require_user_profile_read(self, *, actor: User, target_user_id: uuid.UUID) -> User:
        if not can_read_user_profile(actor=actor, target_user_id=target_user_id):
            raise ForbiddenError()
        user = self._db.get(User, target_user_id)
        if user is None or user.is_deleted:
            raise NotFoundError()
        return user

    def require_user_profile_mutate(self, *, actor: User, target_user_id: uuid.UUID) -> User:
        if not can_mutate_user_profile(actor=actor, target_user_id=target_user_id):
            raise ForbiddenError()
        user = self._db.get(User, target_user_id)
        if user is None or user.is_deleted:
            raise NotFoundError()
        return user

    def require_league_create(self, *, actor: User) -> None:
        if not can_create_league(actor=actor):
            raise EmailNotVerifiedError()

    def get_membership(
        self,
        *,
        actor: User,
        league_id: uuid.UUID,
    ) -> LeagueMembership | None:
        return self._db.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.user_id == actor.id,
            )
        )

    def require_league_read(
        self,
        *,
        actor: User,
        league_id: uuid.UUID,
    ) -> tuple[League, LeagueMembership | None]:
        league = self._db.get(League, league_id)
        if league is None:
            raise NotFoundError()
        membership = self.get_membership(actor=actor, league_id=league_id)
        if not can_read_league(actor=actor, membership=membership):
            raise ForbiddenError()
        return league, membership

    def require_league_update(
        self,
        *,
        actor: User,
        league_id: uuid.UUID,
    ) -> tuple[League, LeagueMembership | None]:
        league = self._db.get(League, league_id)
        if league is None:
            raise NotFoundError()
        membership = self.get_membership(actor=actor, league_id=league_id)
        if not can_update_league(actor=actor, membership=membership):
            raise ForbiddenError()
        return league, membership

    def require_data_export(self, *, actor: User, target_user_id: uuid.UUID) -> User:
        if not can_export_own_data(actor=actor, target_user_id=target_user_id):
            raise ForbiddenError()
        user = self._db.get(User, target_user_id)
        if user is None:
            raise NotFoundError()
        return user

    def require_account_delete(self, *, actor: User, target_user_id: uuid.UUID) -> User:
        if not can_delete_own_account(actor=actor, target_user_id=target_user_id):
            raise ForbiddenError()
        user = self._db.get(User, target_user_id)
        if user is None:
            raise NotFoundError()
        return user
