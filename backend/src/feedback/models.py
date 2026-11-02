"""Modelli ORM delle segnalazioni utente e dei loro allegati."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime

CATEGORIES = ("bug", "suggerimento", "altro")
STATUSES = ("new", "in_review", "resolved", "dismissed")
PLATFORMS = ("web", "android", "ios")
ATTACHMENT_KINDS = ("image", "video")


class FeedbackReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Una segnalazione scritta da un utente: visibile solo a lui e agli operatori."""

    __tablename__ = "feedback_reports"
    __table_args__ = (
        CheckConstraint("category in ('bug','suggerimento','altro')", name="category"),
        CheckConstraint("status in ('new','in_review','resolved','dismissed')", name="status"),
        Index("ix_feedback_reports_status_created_at", "status", "created_at"),
        Index("ix_feedback_reports_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="bug")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Contesto tecnico utile a riprodurre il problema (nessun dato personale).
    page_context: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    operator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    handled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    attachments: Mapped[list[FeedbackAttachment]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="FeedbackAttachment.created_at",
    )


class FeedbackAttachment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immagine o video allegato a una segnalazione (file su disco privato)."""

    __tablename__ = "feedback_attachments"
    __table_args__ = (
        CheckConstraint("kind in ('image','video')", name="kind"),
        Index("ix_feedback_attachments_report_id", "report_id"),
    )

    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Nome del file su disco: `<id>.<estensione>`, mai il nome scelto dall'utente.
    stored_name: Mapped[str] = mapped_column(String(80), nullable=False)

    report: Mapped[FeedbackReport] = relationship(back_populates="attachments")
