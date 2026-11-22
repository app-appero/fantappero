"""ORM: statistiche stagionali dei calciatori e registro delle chiamate di import (1.3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime


class AthleteSeasonStat(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Una riga per calciatore + stagione + club + competizione (e fonte).

    ``source = 'provider'``: statistiche di stagione del fornitore (``/players``), importate una
    volta per le stagioni concluse. ``source = 'fantappero'``: aggregato dei nostri dati per
    partita (``player_match_stats`` + voti ``player_match_ratings``), riscritto a ogni ricalcolo
    della stagione in corso. Un trasferimento a metà stagione dà due righe.

    La chiave è sugli id del fornitore (``athlete_provider_id``, ``club_provider_id``,
    ``competition_provider_id``; ``0`` = sconosciuto) perché il fornitore riporta anche club,
    campionati e calciatori che da noi non esistono: gli id nostri (``athlete_id``, ``club_id``,
    ``competition_id``) si valorizzano quando ci sono, altrimenti restano i nomi.
    """

    __tablename__ = "athlete_season_stats"
    __table_args__ = (
        UniqueConstraint(
            "athlete_provider_id",
            "season_year",
            "source",
            "club_provider_id",
            "competition_provider_id",
            name="uq_athlete_season_stats_row",
        ),
        CheckConstraint("source IN ('provider', 'fantappero')", name="source"),
        Index("ix_athlete_season_stats_season_year_source", "season_year", "source"),
    )

    athlete_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    club_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )
    club_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    competition_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    competition_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("competitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    competition_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    appearances: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lineups: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Media voto: per il fornitore ``games.rating`` (la sua media di stagione), per FantApperò
    #: la media dei nostri voti (``display``) nelle partite con voto.
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: Partite con voto FantApperò (solo ``source = 'fantappero'``).
    votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fantasy_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals_conceded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    penalties_saved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Porte inviolate dei portieri: solo FantApperò (il fornitore non le dà nell'aggregato).
    clean_sheets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )


class AthleteSeasonImportFetch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registro delle chiamate già fatte dall'import dello storico (riprendibile).

    Una riga per pagina di campionato (``/players?league&season&page``) o per calciatore cercato
    uno per uno (``/players?id&season``), anche quando il fornitore non ha restituito nulla: una
    seconda esecuzione salta quello che c'è già e non spende quota.
    """

    __tablename__ = "athlete_season_import_fetches"
    __table_args__ = (
        UniqueConstraint("request_key", name="uq_athlete_season_import_fetches_request_key"),
        Index("ix_athlete_season_import_fetches_season_year_kind", "season_year", "kind"),
    )

    request_key: Mapped[str] = mapped_column(String(96), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    competition_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    athlete_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
