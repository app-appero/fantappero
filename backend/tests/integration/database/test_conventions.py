"""Unit tests for ORM conventions (no live database)."""

from __future__ import annotations

from database.base import NAMING_CONVENTION, Base, SoftDeleteMixin, TimestampMixin
from database.models.infrastructure import SystemFlag


def test_naming_convention_keys() -> None:
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}


def test_baseline_table_registered() -> None:
    assert "system_flags" in Base.metadata.tables


def test_system_flag_columns() -> None:
    table = Base.metadata.tables["system_flags"]
    column_names = {column.name for column in table.columns}
    assert column_names == {"id", "key", "value", "scope", "created_at", "updated_at"}


def test_system_flag_indexes_and_constraints() -> None:
    table = Base.metadata.tables["system_flags"]
    assert any(constraint.name == "uq_system_flags_key" for constraint in table.constraints)
    index_names = {index.name for index in table.indexes}
    assert "ix_system_flags_scope" in index_names


def test_soft_delete_mixin_is_optional() -> None:
    assert not issubclass(SystemFlag, SoftDeleteMixin)


def test_timestamp_mixin_present() -> None:
    assert issubclass(SystemFlag, TimestampMixin)
