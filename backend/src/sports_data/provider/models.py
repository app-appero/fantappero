"""ORM model for raw provider payload snapshots (EP04-01)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime


class ProviderSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Content-addressed raw provider response retained for audit / reprocessing.

    Idempotency key: ``(provider, endpoint, request_fingerprint, payload_hash)``.
    A changed payload for the same request produces a new row (history), never a delete.
    """

    __tablename__ = "provider_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "endpoint",
            "request_fingerprint",
            "payload_hash",
            name="uq_provider_snapshots_content",
        ),
        Index("ix_provider_snapshots_fetched_at", "fetched_at"),
        Index("ix_provider_snapshots_endpoint", "provider", "endpoint"),
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )
    page_current: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    page_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
