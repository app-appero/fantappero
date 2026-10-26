"""ORM models for the in-app notification center (EP09-01) and push delivery (EP09-05)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import NotificationCategory, NotificationStatus
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One in-app notification for a user (EP09-01 / EP09-02..05 producers)."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_notifications_user_dedup"),
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_user_id_read_at", "user_id", "read_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[NotificationCategory] = mapped_column(
        Enum(
            NotificationCategory,
            name="notification_category",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(
            NotificationStatus,
            name="notification_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'delivered'"),
    )
    template_key: Mapped[str] = mapped_column(nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    dedup_key: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(nullable=False)
    deep_link: Mapped[str | None] = mapped_column(nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship()


class NotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-user, per-category in-app opt-out (EP09-01). Channel columns land in EP09-05."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_notification_preferences_user_category"),
        Index("ix_notification_preferences_user_id", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[NotificationCategory] = mapped_column(
        Enum(
            NotificationCategory,
            name="notification_category",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    in_app_enabled: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))

    user: Mapped[User] = relationship()


class NotificationEventPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-user, per-event granular opt-out, canali in-app/push separati (TASK5).

    Più fine di ``NotificationPreference`` (quella resta per categoria, es.
    spegnere tutto «risultati»): qui l'utente può spegnere solo i gol e
    tenere l'ammonizione, o tenere l'in-app e spegnere solo la push su un
    singolo evento. ``event_key`` è definito in
    ``notifications/event_catalog.py`` e raggruppa uno o più ``template_key``.

    Nessuna riga per (user_id, event_key) = tutto attivo: è il default per
    chi non ha ancora toccato le preferenze granulari.
    """

    __tablename__ = "notification_event_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "event_key", name="uq_notification_event_preferences_user_event"
        ),
        Index("ix_notification_event_preferences_user_id", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    push_enabled: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))

    user: Mapped[User] = relationship()


class PushDevice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Expo push token for one installed app instance (EP09-05).

    Keyed by ``token``, not by ``user_id`` + ``token``: a reinstall or a
    different account logging into the same device must move the token to
    the new owner, not create a duplicate row that still points at the old
    one.
    """

    __tablename__ = "push_devices"
    __table_args__ = (
        UniqueConstraint("token", name="uq_push_devices_token"),
        Index("ix_push_devices_user_id", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    #: Non nullo quando Expo segnala il token come non più registrato
    #: (disinstallazione): smettiamo di provare a mandarci push.
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship()


class NotificationBroadcast(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Avviso inviato (o programmato) da un operatore a un pubblico scelto (EP09-06).

    Letti e consegnati non sono colonne: si ricavano dalle notifiche create,
    la cui ``dedup_key`` inizia per ``broadcast:<id>:``.
    """

    __tablename__ = "notification_broadcasts"
    __table_args__ = (
        Index("ix_notification_broadcasts_status_scheduled_at", "status", "scheduled_at"),
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    channels: Mapped[dict[str, bool]] = mapped_column(JSONB, nullable=False)
    audience: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    audience_label: Mapped[str] = mapped_column(String(200), nullable=False)
    #: ``scheduled`` -> ``sending`` -> ``sent``; oppure ``cancelled``.
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    push_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class OperatorEmailLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """History of operator-composed emails sent from the portal (Task 6c).

    Separate from ``NotificationBroadcast``: this is a direct email send (not
    an in-app notification), so there is no delivered/read count to derive —
    only who sent it, to whom, and when.
    """

    __tablename__ = "operator_email_logs"
    __table_args__ = (Index("ix_operator_email_logs_sent_at", "sent_at"),)

    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    audience_label: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
