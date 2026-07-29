"""Declarative base, naming conventions, and shared mixins."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from database.types import UTCDateTime, uuid_pk_column

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Application ORM base with PostgreSQL naming conventions."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """UUID primary key generated in the database."""

    id: Mapped[Any] = uuid_pk_column()


class TimestampMixin:
    """Audit timestamps stored as UTC ``timestamptz``."""

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text("timezone('utc', now())"),
        onupdate=lambda: datetime.now(UTC),
    )


class SoftDeleteMixin:
    """Opt-in soft delete via nullable ``deleted_at`` (UTC)."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class TableNameMixin:
    """Plural ``snake_case`` table names derived from class name."""

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
        return re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", snake).lower()

    @staticmethod
    def _pluralize(snake: str) -> str:
        if snake.endswith("y"):
            return f"{snake[:-1]}ies"
        if snake.endswith("s"):
            return f"{snake}es"
        return f"{snake}s"

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return cls._pluralize(cls._camel_to_snake(cls.__name__))
