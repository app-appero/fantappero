"""League audit trail for configuration actions (EP03-01)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TableNameMixin, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import LeagueAuditAction

league_audit_action_enum = ENUM(
    LeagueAuditAction,
    name="league_audit_action",
    create_type=False,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class LeagueAuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin, Base):
    """Immutable record of a league configuration action (no PII in payload)."""

    league_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[LeagueAuditAction] = mapped_column(
        league_audit_action_enum,
        nullable=False,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
