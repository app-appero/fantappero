"""Precedence constants for events vs player stats (see event_precedence_rules.md)."""

from __future__ import annotations

# Primary source for each scoring kind.
PRIMARY_SOURCE: dict[str, str] = {
    "goal": "events",
    "penalty_scored": "events",
    "own_goal": "events",
    "assist": "events",
    "penalty_missed": "events",  # preferred; stats fill when events omit Missed Penalty
    "penalty_off_target": "events",
    "penalty_saved": "players",  # no events.detail for save in API-Football corpus
}

# Stats must never invent these when events already carry them.
NO_DUPLICATE_FROM_STATS = frozenset({"goal", "penalty_scored", "own_goal", "assist"})

GOAL_DETAILS_FROM_EVENTS = frozenset({"Normal Goal", "Penalty", "Own Goal", "Missed Penalty"})
