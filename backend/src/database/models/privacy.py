"""Privacy audit trail for data export and account deletion (EP02-04)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TableNameMixin, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import PrivacyAuditAction

privacy_audit_action_enum = ENUM(
    PrivacyAuditAction,
    name="privacy_audit_action",
    create_type=False,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class PrivacyAuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin, Base):
    """Immutable record of a privacy-related action (no PII in payload)."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[PrivacyAuditAction] = mapped_column(
        privacy_audit_action_enum,
        nullable=False,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
