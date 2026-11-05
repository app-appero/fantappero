"""Lista nera degli account: chi è bloccato non può accedere né registrarsi di nuovo."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from auth.exceptions import AccountBlockedError, ValidationAuthError
from auth.models.blocked_account import BlockedAccount
from auth.validators import validate_email


class BlockList:
    def __init__(self, session: Session) -> None:
        self._session = session

    def is_blocked(self, email: str) -> bool:
        return (
            self._session.scalar(
                select(BlockedAccount.id).where(BlockedAccount.email == email.strip().lower())
            )
            is not None
        )

    def assert_not_blocked(self, email: str) -> None:
        if self.is_blocked(email):
            raise AccountBlockedError()

    def list_entries(self) -> list[BlockedAccount]:
        return list(
            self._session.scalars(
                select(BlockedAccount).order_by(BlockedAccount.created_at.desc())
            ).all()
        )

    def add(self, email: str, *, reason: str | None, actor_id: UUID | None) -> BlockedAccount:
        normalized = validate_email(email)
        existing = self._session.scalar(
            select(BlockedAccount).where(BlockedAccount.email == normalized)
        )
        if existing is not None:
            return existing
        cleaned = (reason or "").strip()[:500] or None
        entry = BlockedAccount(email=normalized, reason=cleaned, created_by_user_id=actor_id)
        self._session.add(entry)
        self._session.flush()
        return entry

    def remove(self, entry_id: UUID) -> None:
        result = self._session.execute(delete(BlockedAccount).where(BlockedAccount.id == entry_id))
        if result.rowcount == 0:
            raise ValidationAuthError(
                "Voce non trovata nella lista nera.", code="blocked_not_found"
            )
