"""Registro degli aggiornamenti del listone (release 1.4, «Da guardare» del Riepilogo).

Prima la data dell'ultimo aggiornamento stava solo in Redis, per un'ora dopo il giro
(``leagues.listone_refresh_progress``). Qui ogni aggiornamento riuscito lascia una riga per
sempre: quando, chi, da dove (pannello operatore o pagina della lega) e quanti calciatori
sono entrati, usciti o cambiati.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: Aggiornamento dal fornitore (pannello operatore o lega), ruoli presi dal fornitore dopo la
#: conferma dell'operatore, ruoli ripristinati dall'operatore.
LISTONE_UPDATE_KINDS = ("refresh", "roles_from_provider", "roles_restored")
LISTONE_UPDATE_SOURCES = ("operator", "league")


class ListoneUpdate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Un aggiornamento riuscito del listone ufficiale di una stagione."""

    __tablename__ = "listone_updates"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('refresh', 'roles_from_provider', 'roles_restored')", name="kind"
        ),
        CheckConstraint("source IN ('operator', 'league')", name="source"),
        Index("ix_listone_updates_created_at", "created_at"),
    )

    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Nome dell'autore al momento dell'aggiornamento: resta anche se l'account sparisce.
    actor_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    league_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True
    )
    #: Nome della lega da cui è partito l'aggiornamento (solo ``source == "league"``).
    league_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
