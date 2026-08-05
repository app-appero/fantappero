"""League membership ORM model (EP02-01 / EP02-04)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import LeagueMemberRole

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League


class LeagueMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User membership in a private league with a tenant-scoped role."""

    __tablename__ = "league_memberships"
    __table_args__ = (
        UniqueConstraint("league_id", "user_id", name="uq_league_memberships_league_id_user_id"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[LeagueMemberRole] = mapped_column(
        Enum(
            LeagueMemberRole,
            name="league_member_role",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    historical_display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    league: Mapped[League] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="league_memberships")
