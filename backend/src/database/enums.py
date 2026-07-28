"""PostgreSQL-backed enum types for baseline schema."""

from __future__ import annotations

import enum


class FlagScope(str, enum.Enum):
    """Scope for infrastructural feature flags."""

    SYSTEM = "system"
    TENANT = "tenant"
