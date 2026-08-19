"""Infrastructural baseline tables (no product domain entities)."""

from __future__ import annotations

from sqlalchemy import Enum, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TableNameMixin, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import FlagScope


class SystemFlag(Base, UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin):
    """Key/value feature flags for runtime infrastructure toggles."""

    __tablename__ = "system_flags"
    __table_args__ = (Index("ix_system_flags_scope", "scope"),)

    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[FlagScope] = mapped_column(
        Enum(
            FlagScope,
            name="flag_scope",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'system'"),
    )
