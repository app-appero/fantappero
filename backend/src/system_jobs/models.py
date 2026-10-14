"""Override operatore dei job periodici."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin
from database.types import UTCDateTime


class SystemJob(Base, TimestampMixin):
    """Accensione e frequenza di un job del beat, modificabili dal pannello."""

    __tablename__ = "system_jobs"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    last_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
