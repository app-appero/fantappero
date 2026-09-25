"""Player availability sync from ``/injuries`` (OQ-11)."""

from sports_data.availability.classify import KNOWN_REASONS, classify_availability_reason
from sports_data.availability.models import PlayerAvailability
from sports_data.availability.sync import (
    AVAILABILITY_SYNC_ENTITIES_TOTAL,
    AvailabilitySyncCounters,
    is_confirmed_unavailable,
    sync_player_availabilities,
    upsert_player_availability,
)

__all__ = [
    "AVAILABILITY_SYNC_ENTITIES_TOTAL",
    "AvailabilitySyncCounters",
    "KNOWN_REASONS",
    "PlayerAvailability",
    "classify_availability_reason",
    "is_confirmed_unavailable",
    "sync_player_availabilities",
    "upsert_player_availability",
]
