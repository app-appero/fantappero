"""Normalized competition catalog (EP03-01)."""

from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TableNameMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Competition(UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin, Base):
    """Provider-backed competition available for league configuration."""

    __table_args__ = (UniqueConstraint("provider_id", name="uq_competitions_provider_id"),)

    provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
