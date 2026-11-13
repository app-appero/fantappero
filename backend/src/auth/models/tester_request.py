"""Richieste di accesso al pilota di chi non è ancora tester (modalità test)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TesterAccessRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Una richiesta per indirizzo email (verificato da Google). Non è un account."""

    __tablename__ = "tester_access_requests"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Solo per aggiungere la persona al gruppo WhatsApp dei tester: mai altri usi.
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    motivation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
