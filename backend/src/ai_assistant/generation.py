"""Deterministic language generation for AI-assisted advice (EP10-01).

Deliberately not backed by an external LLM: no provider key/secret exists in
this environment, and the shared card scope ("Separare recupero dati, regole
deterministiche e generazione linguistica") only requires the generation
step to be an isolated, swappable port — not that it call a remote model.
``MODEL_VERSION`` below is the audited "model" identity for this port; a
future card can swap the implementation without touching callers or the
audit schema (``AiInteraction.model_version`` already carries this value).
"""

from __future__ import annotations

MODEL_VERSION = "deterministic-rules-v1"


def format_rating(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "n/d"


def format_minutes(value: float | None) -> str:
    return f"{value:.0f}'" if value is not None else "n/d"
