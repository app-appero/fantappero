"""Lista dei tester autorizzati ad accedere durante la «modalità test» del pilota."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TesterAllowlistEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Un indirizzo email (minuscolo) autorizzato, anche prima del primo accesso."""

    __tablename__ = "tester_allowlist"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
