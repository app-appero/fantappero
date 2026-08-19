"""Internal types for fantavoto-relevant event normalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ScoringEventKind(str, Enum):
    """Normalized kinds that can modify the fantavoto (bonus/malus).

    Scoring deltas are NOT applied here — EP00-03 only classifies events.
    """

    GOAL = "goal"
    PENALTY_SCORED = "penalty_scored"
    OWN_GOAL = "own_goal"
    ASSIST = "assist"
    PENALTY_MISSED = "penalty_missed"
    PENALTY_SAVED = "penalty_saved"
    PENALTY_OFF_TARGET = "penalty_off_target"
    UNKNOWN = "unknown"


class EventStatus(str, Enum):
    """Resolution state after precedence / reconciliation."""

    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    ANOMALY = "anomaly"
    INSUFFICIENT = "insufficient"


class AnomalyCode(str, Enum):
    """Machine-readable reasons when sources disagree or are incomplete."""

    GOAL_COUNT_MISMATCH = "goal_count_mismatch"
    ASSIST_COUNT_MISMATCH = "assist_count_mismatch"
    PENALTY_SCORED_MISMATCH = "penalty_scored_mismatch"
    EVENTS_MISSING_MISSED_PENALTY = "events_missing_missed_penalty"
    ORPHAN_PENALTY_SAVE = "orphan_penalty_save"
    ORPHAN_PENALTY_MISS = "orphan_penalty_miss"
    MISSING_PLAYER_ID = "missing_player_id"
    UNKNOWN_GOAL_DETAIL = "unknown_goal_detail"
    STATS_ONLY_GOAL = "stats_only_goal"
    STATS_ONLY_ASSIST = "stats_only_assist"


@dataclass(frozen=True)
class NormalizedScoringEvent:
    """Internal match_event candidate for scoring (no points applied)."""

    provider_event_key: str
    fixture_id: int
    kind: ScoringEventKind
    status: EventStatus
    player_id: int | None
    team_id: int | None
    related_player_id: int | None = None
    related_team_id: int | None = None
    minute_elapsed: int | None = None
    minute_extra: int | None = None
    sources: tuple[str, ...] = ()
    anomaly_codes: tuple[AnomalyCode, ...] = ()
    raw_type: str | None = None
    raw_detail: str | None = None
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_event_key": self.provider_event_key,
            "fixture_id": self.fixture_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "player_id": self.player_id,
            "team_id": self.team_id,
            "related_player_id": self.related_player_id,
            "related_team_id": self.related_team_id,
            "minute_elapsed": self.minute_elapsed,
            "minute_extra": self.minute_extra,
            "sources": list(self.sources),
            "anomaly_codes": [c.value for c in self.anomaly_codes],
            "raw_type": self.raw_type,
            "raw_detail": self.raw_detail,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class NormalizationResult:
    """Deterministic output of one normalize pass over a fixture."""

    fixture_id: int
    events: tuple[NormalizedScoringEvent, ...]
    anomalies: tuple[AnomalyCode, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def has_blocking_anomaly(self) -> bool:
        return bool(self.anomalies) or any(
            e.status in (EventStatus.ANOMALY, EventStatus.INSUFFICIENT) for e in self.events
        )
