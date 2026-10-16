"""Snapshot delle formazioni probabili. Non sostituiscono le formazioni ufficiali."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime


class FotmobFixtureLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Corrispondenza esplicita tra una fixture interna e un match FotMob."""

    __tablename__ = "fotmob_fixture_links"
    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fotmob_fixture_links_fixture_id"),
        UniqueConstraint("fotmob_match_id", name="uq_fotmob_fixture_links_fotmob_match_id"),
    )

    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
    )
    fotmob_match_id: Mapped[int] = mapped_column(Integer, nullable=False)
    home_name: Mapped[str] = mapped_column(String(160), nullable=False)
    away_name: Mapped[str] = mapped_column(String(160), nullable=False)


class PredictedLineupSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Una lettura nel tempo. Le formazioni ufficiali non sovrascrivono queste righe."""

    __tablename__ = "predicted_lineup_snapshots"

    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fotmob_match_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lineup_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reliability: Mapped[str] = mapped_column(String(32), nullable=False)
    warning_codes: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    home_formation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    away_formation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    home_coach: Mapped[str | None] = mapped_column(String(160), nullable=True)
    away_coach: Mapped[str | None] = mapped_column(String(160), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)

    players: Mapped[list[PredictedLineupPlayer]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class PredictedLineupPlayer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Titolare, panchinaro o indisponibile dentro uno snapshot."""

    __tablename__ = "predicted_lineup_players"

    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("predicted_lineup_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )
    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    shirt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fotmob_player_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_unavailable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    unavailability_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unavailability_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    blocks_selection: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    grid: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    snapshot: Mapped[PredictedLineupSnapshot] = relationship(back_populates="players")
