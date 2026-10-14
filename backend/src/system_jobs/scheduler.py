"""Beat scheduler che rilegge accensione e frequenza dal database."""

from __future__ import annotations

import time
from datetime import timedelta

from celery.beat import PersistentScheduler
from celery.schedules import schedule as interval_schedule

from config.settings.loader import get_api_settings
from database.session import (
    create_engine_from_url,
    create_session_factory,
    session_scope,
)
from observability.logging import get_logger
from system_jobs.schedule_sync import sync_schedule_entries
from system_jobs.service import beat_schedule_dict

logger = get_logger(__name__)


class SystemJobScheduler(PersistentScheduler):
    """Schedule di ambiente all'avvio, poi override del pannello operatore.

    Il rilettura è al massimo ogni 15 secondi: un interruttore o una nuova
    frequenza valgono senza riavviare il beat. `max_interval` tiene il
    processo sveglio anche quando il job più frequente è spento.
    """

    max_interval = 30

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._reloaded_at = 0.0
        super().__init__(*args, **kwargs)

    def setup_schedule(self) -> None:
        super().setup_schedule()
        self._apply_operator_schedule()

    def tick(self, *args: object, **kwargs: object) -> float:
        now = time.monotonic()
        if now - self._reloaded_at >= 15:
            self._reloaded_at = now
            self._apply_operator_schedule()
        return super().tick(*args, **kwargs)

    def _apply_operator_schedule(self) -> None:
        try:
            settings = get_api_settings()
            engine = create_engine_from_url(settings.database_url)
            factory = create_session_factory(engine)
            try:
                with session_scope(factory) as session:
                    desired = beat_schedule_dict(session)
            finally:
                engine.dispose()
        except Exception:
            logger.exception("system_job_schedule_reload_failed")
            return

        def make_entry(key: str, spec: dict[str, object]) -> object:
            seconds = float(spec["schedule"])  # type: ignore[arg-type]
            return self.Entry(
                name=key,
                task=str(spec["task"]),
                schedule=interval_schedule(run_every=timedelta(seconds=seconds)),
                kwargs=dict(spec.get("kwargs") or {}),
                options=dict(spec.get("options") or {}),
                app=self.app,
            )

        try:
            sync_schedule_entries(
                self.schedule,
                desired,
                make_entry=make_entry,
                interval_schedule=interval_schedule,
            )
        except Exception:
            logger.exception("system_job_schedule_apply_failed")
            return
        self._reloaded_at = time.monotonic()
