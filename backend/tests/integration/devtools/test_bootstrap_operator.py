"""Integration tests for the operator bootstrap devtools command (EP11-04a)."""

from __future__ import annotations

import secrets

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from auth.models.user import User
from auth.security import hash_password
from database.enums import PlatformRole, UserType
from devtools.bootstrap_operator import bootstrap_operator


@pytest.fixture(autouse=True)
def _clean_users(session: Session) -> None:
    session.execute(delete(User))
    session.commit()


def _create_user(session: Session, *, email: str, platform_role: PlatformRole) -> User:
    user = User(
        email=email,
        password_hash=hash_password(secrets.token_urlsafe(24)),
        platform_role=platform_role,
        user_type=UserType.HUMAN,
    )
    session.add(user)
    session.commit()
    return user


def test_bootstrap_promotes_registered_user(session: Session) -> None:
    user = _create_user(
        session, email="future.operator@example.com", platform_role=PlatformRole.USER
    )

    message = bootstrap_operator(session, email="future.operator@example.com")

    session.refresh(user)
    assert user.platform_role == PlatformRole.OPERATOR
    assert "Promoted" in message


def test_bootstrap_is_case_insensitive(session: Session) -> None:
    user = _create_user(session, email="Mixed.Case@example.com", platform_role=PlatformRole.USER)

    bootstrap_operator(session, email="mixed.case@example.com")

    session.refresh(user)
    assert user.platform_role == PlatformRole.OPERATOR


def test_bootstrap_is_noop_when_operator_already_exists(session: Session) -> None:
    _create_user(
        session, email="existing.operator@example.com", platform_role=PlatformRole.OPERATOR
    )
    other = _create_user(
        session, email="should.not.change@example.com", platform_role=PlatformRole.USER
    )

    message = bootstrap_operator(session, email="should.not.change@example.com")

    session.refresh(other)
    assert other.platform_role == PlatformRole.USER
    assert "no-op" in message


def test_bootstrap_fails_for_unregistered_email(session: Session) -> None:
    with pytest.raises(ValueError, match="Register the account first"):
        bootstrap_operator(session, email="nobody@example.com")
