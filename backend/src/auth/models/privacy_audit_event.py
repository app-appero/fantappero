"""Privacy audit event ORM model (EP02-04)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import PrivacyAuditAction

if TYPE_CHECKING:
    from auth.models.user import User


class PrivacyAuditEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable audit row for data export and account deletion."""

    __tablename__ = "privacy_audit_events"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[PrivacyAuditAction] = mapped_column(
        Enum(
            PrivacyAuditAction,
            name="privacy_audit_action",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    actor: Mapped[User] = relationship(foreign_keys=[actor_id])
