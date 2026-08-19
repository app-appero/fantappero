"""Deterministic normalization of fantavoto-relevant match events (EP00-03)."""

from sports_data.normalization.events import normalize_scoring_events
from sports_data.normalization.types import (
    AnomalyCode,
    EventStatus,
    NormalizationResult,
    NormalizedScoringEvent,
    ScoringEventKind,
)

__all__ = [
    "AnomalyCode",
    "EventStatus",
    "NormalizationResult",
    "NormalizedScoringEvent",
    "ScoringEventKind",
    "normalize_scoring_events",
]
