"""Competition catalog ORM model (EP03-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from leagues.models.league import League


class Competition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalized competition from the sports data provider catalog."""

    __tablename__ = "competitions"

    provider_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)

    leagues: Mapped[list[League]] = relationship(
        secondary="league_competitions",
        back_populates="competitions",
    )
