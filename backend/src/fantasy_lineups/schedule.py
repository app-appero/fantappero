"""Celery beat entry per la formazione automatica IA (EP13-P05)."""

from __future__ import annotations


def ai_lineups_beat_schedule(
    *,
    enabled: bool,
    interval_seconds: int = 1800,
) -> dict[str, dict]:
    """Pianifica la generazione ricorrente delle formazioni IA.

    ``expires`` pari all'intervallo evita che esecuzioni accodate si
    sovrappongano: il task è idempotente, ma non serve rieseguirlo in coda.
    """
    if not enabled:
        return {}
    return {
        "fantasy-lineups-generate-ai": {
            "task": "fantasy_lineups.generate_ai",
            "schedule": float(interval_seconds),
            "options": {"expires": float(interval_seconds)},
        },
    }
