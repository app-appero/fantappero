"""Applica uno schedule desiderato senza azzerare l'ultima esecuzione."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from datetime import timedelta
from typing import Any


def sync_schedule_entries(
    current: MutableMapping[str, Any],
    desired: dict[str, dict[str, object]],
    *,
    make_entry: Callable[[str, dict[str, object]], Any],
    interval_schedule: Callable[..., Any],
) -> None:
    """Allinea `current` a `desired`.

    Un job spento viene tolto. Un job acceso già presente cambia solo la
    frequenza, così Celery non lo considera mai eseguito e non lo rilancia
    subito a ogni rilettura.
    """
    for key in list(current):
        if key not in desired:
            current.pop(key, None)
    for key, spec in desired.items():
        seconds = float(spec["schedule"])  # type: ignore[arg-type]
        existing = current.get(key)
        if existing is None:
            current[key] = make_entry(key, spec)
            continue
        run_every = getattr(getattr(existing, "schedule", None), "run_every", None)
        target = timedelta(seconds=seconds)
        if run_every != target:
            existing.schedule = interval_schedule(run_every=target)
        existing.task = spec["task"]
        existing.kwargs = dict(spec.get("kwargs") or {})
        options = spec.get("options") or {}
        existing.options = dict(options) if isinstance(options, dict) else {}
