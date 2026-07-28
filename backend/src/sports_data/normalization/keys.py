"""Stable provider_event_key composition (OQ-06 / G-05)."""

from __future__ import annotations

from typing import Any


def _token(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def event_provider_key(
    *,
    fixture_id: int,
    elapsed: Any,
    extra: Any,
    type_: Any,
    detail: Any,
    player_id: Any,
    assist_id: Any = None,
    role: str = "primary",
) -> str:
    """Compose a deterministic key for an events-endpoint row (or derived sibling).

    Provider does not expose a stable event id. Composition is the ACL key for
    idempotent upserts. Role distinguishes goal vs assist derived from the same row.
    """
    return "|".join(
        [
            "events",
            _token(fixture_id),
            _token(elapsed),
            _token(extra),
            _token(type_),
            _token(detail),
            _token(player_id),
            _token(assist_id),
            role,
        ]
    )


def stats_provider_key(
    *,
    fixture_id: int,
    kind: str,
    player_id: Any,
    ordinal: int = 0,
) -> str:
    """Compose a key for stats-only derived scoring events (e.g. penalty.saved)."""
    return "|".join(
        [
            "players",
            _token(fixture_id),
            kind,
            _token(player_id),
            _token(ordinal),
        ]
    )
