"""League audit event ORM model (EP03-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import LeagueAuditAction

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League


class LeagueAuditEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable audit row for league configuration changes."""

    __tablename__ = "league_audit_events"

    league_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("leagues.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[LeagueAuditAction] = mapped_column(
        Enum(
            LeagueAuditAction,
            name="league_audit_action",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    league: Mapped[League] = relationship()
    actor: Mapped[User | None] = relationship()
