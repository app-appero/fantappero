"""ORM model for player availability from ``/injuries`` (OQ-11)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime

if TYPE_CHECKING:
    from sports_data.catalog.models import Club
    from sports_data.fixtures.models import Fixture
    from sports_data.roster.models import Athlete


class PlayerAvailability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Voce ``/injuries`` normalizzata: presenza confermata di indisponibilità.

    ``provider_key`` è l'identità naturale del provider per l'idempotenza
    (stesso atleta + stessa fixture = stesso record). **L'assenza di un
    record per un atleta non implica disponibilità**: il provider può non
    segnalare un giocatore realmente infortunato (verificato con un caso
    reale, OQ-11). Chi consuma questa tabella deve trattare "nessun record"
    come "sconosciuto", mai come "disponibile per certo".
    """

    __tablename__ = "player_availabilities"
    __table_args__ = (
        UniqueConstraint("provider_key", name="uq_player_availabilities_provider_key"),
    )

    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    athlete_provider_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )
    club_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fixture_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competition_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status_type_raw: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_raw: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(160), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    athlete: Mapped[Athlete | None] = relationship()
    club: Mapped[Club | None] = relationship()
    fixture: Mapped[Fixture | None] = relationship()
