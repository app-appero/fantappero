"""Uso dell'app per utente: piattaforma, versione, prima e ultima volta (release 1.4).

Una riga per (utente, piattaforma), scritta dal backend a partire dalle richieste dell'app
(``app_usage.recorder``): dalla 1.4 l'app manda la sua versione in ogni richiesta; delle app
più vecchie si sa solo che sono app (User-Agent ``okhttp/``) o app dalla 1.2 in poi (chiamano
``GET /app/version``). Serve all'elenco «chi ha quale versione» del pannello operatore e a non
mandare la notifica di una nuova versione a chi ce l'ha già.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime

#: Versione esatta dalle intestazioni ``X-App-Version`` / ``X-App-Version-Code`` (app 1.4+).
SOURCE_HEADER = "header"
#: ``GET /app/version`` senza intestazioni: app 1.2 o 1.3, versione non nota.
SOURCE_VERSION_CHECK = "version_check"
#: Altra richiesta con User-Agent ``okhttp/`` e senza intestazioni: app, versione non nota.
SOURCE_USER_AGENT = "user_agent"
APP_USAGE_SOURCES = (SOURCE_HEADER, SOURCE_VERSION_CHECK, SOURCE_USER_AGENT)
#: Quanto è precisa ogni fonte: una meno precisa non cancella mai una più precisa.
SOURCE_RANK = {SOURCE_USER_AGENT: 1, SOURCE_VERSION_CHECK: 2, SOURCE_HEADER: 3}

PLATFORM_ANDROID = "android"
PLATFORM_IOS = "ios"
APP_PLATFORMS = (PLATFORM_ANDROID, PLATFORM_IOS)


class UserAppUsage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """L'app di un utente su una piattaforma: la versione, o il meglio che se ne sa."""

    __tablename__ = "user_app_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_user_app_usage_user_platform"),
        CheckConstraint("source IN ('header', 'version_check', 'user_agent')", name="source"),
        CheckConstraint("platform IN ('android', 'ios')", name="platform"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Nome della versione, es. ``1.4.0``; vuoto se non si conosce.
    version_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: versionCode Android; vuoto se non si conosce (app 1.3 o precedenti).
    version_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Da dove viene quello che si sa (``APP_USAGE_SOURCES``).
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
