"""Lista nera: indirizzi email che non possono più accedere né registrarsi."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BlockedAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Un indirizzo email (minuscolo) bloccato, ad esempio dopo l'eliminazione di un utente."""

    __tablename__ = "blocked_accounts"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
