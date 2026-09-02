"""ORM models for sports data quality panel (EP04-07)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from sports_data.fixtures.models import Fixture


class SportsDataQualityIssue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Issue di qualità dati sportivi rilevata dallo scan (idempotente per fingerprint)."""

    __tablename__ = "sports_data_quality_issues"

    fingerprint: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'open'"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    fixture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fixture_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    fixture: Mapped[Fixture | None] = relationship()
    sync_retries: Mapped[list[SportsDataSyncRetry]] = relationship(back_populates="issue")


class SportsDataSyncRetry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit di un rilancio sync operatore (atomico e tracciabile)."""

    __tablename__ = "sports_data_sync_retries"

    issue_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sports_data_quality_issues.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fixture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fixture_provider_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'operator_retry'"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'queued'"),
        index=True,
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    counters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    issue: Mapped[SportsDataQualityIssue | None] = relationship(back_populates="sync_retries")
    fixture: Mapped[Fixture | None] = relationship()
    requested_by: Mapped[User | None] = relationship()
