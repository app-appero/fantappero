"""ORM: valore di mercato e media stagionale materializzati per calciatore (1.3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import FantasyRole


class AthleteMarketValue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Valore e media stagionale di un calciatore del listone, per stagione.

    Indipendente dalla lega: ``reference_value`` è in crediti per il budget di riferimento
    (``market.valuation.REFERENCE_BUDGET``); i crediti della lega si ottengono in lettura in
    proporzione al suo budget (``credits_for_budget``). Riscritta da
    ``market.valuation_service.refresh_market_values`` dopo ogni giornata.
    """

    __tablename__ = "athlete_market_values"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id",
            "season_year",
            name="uq_athlete_market_values_athlete_id_season_year",
        ),
        Index("ix_athlete_market_values_season_year", "season_year"),
    )

    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[FantasyRole] = mapped_column(
        Enum(
            FantasyRole,
            name="fantasy_role",
            native_enum=True,
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    #: Indice 0..1 combinato (percentili per stagione nel ruolo, pesati).
    value_index: Mapped[float] = mapped_column(Float, nullable=False)
    #: Crediti per il budget di riferimento, non arrotondati.
    reference_value: Mapped[float] = mapped_column(Float, nullable=False)
    season_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    season_average_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_average_is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    current_votes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    #: Percentili, pesi e medie usati: per spiegare il numero (operatore, test).
    components_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
