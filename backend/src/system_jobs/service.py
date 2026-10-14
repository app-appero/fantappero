"""Lettura e modifica dei job periodici, e costruzione dello schedule beat."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from observability.logging import get_logger
from system_jobs.catalog import SYSTEM_JOBS, SYSTEM_JOBS_BY_KEY, SystemJobSpec
from system_jobs.models import SystemJob

logger = get_logger(__name__)


@dataclass(frozen=True)
class SystemJobView:
    key: str
    title: str
    description: str
    task: str
    enabled: bool
    interval_seconds: int
    min_interval_seconds: int
    max_interval_seconds: int
    last_started_at: datetime | None
    next_run_at: datetime | None

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "task": self.task,
            "enabled": self.enabled,
            "intervalSeconds": self.interval_seconds,
            "minIntervalSeconds": self.min_interval_seconds,
            "maxIntervalSeconds": self.max_interval_seconds,
            "lastStartedAt": self.last_started_at,
            "nextRunAt": self.next_run_at,
        }


def ensure_defaults(session: Session, settings: object | None = None) -> None:
    """Inserisce i job mancanti con i valori d'ambiente (o i default di catalogo)."""
    source = settings if settings is not None else _runtime_settings()
    existing = set(session.scalars(select(SystemJob.key)).all())
    for spec in SYSTEM_JOBS:
        if spec.key in existing:
            continue
        session.add(
            SystemJob(
                key=spec.key,
                enabled=_setting_bool(source, spec.enabled_attr, default=spec.default_enabled),
                interval_seconds=_setting_int(
                    source, spec.interval_attr, default=spec.default_interval_seconds
                ),
            )
        )
    session.flush()


def list_jobs(session: Session) -> list[SystemJobView]:
    ensure_defaults(session)
    rows = {row.key: row for row in session.scalars(select(SystemJob)).all()}
    return [_to_view(spec, rows[spec.key]) for spec in SYSTEM_JOBS if spec.key in rows]


def update_job(
    session: Session,
    key: str,
    *,
    enabled: bool | None = None,
    interval_seconds: int | None = None,
) -> SystemJobView:
    spec = SYSTEM_JOBS_BY_KEY.get(key)
    if spec is None:
        raise ValidationAuthError("Job sconosciuto.", code="system_job_not_found")
    ensure_defaults(session)
    row = session.get(SystemJob, key)
    if row is None:
        raise ValidationAuthError("Job sconosciuto.", code="system_job_not_found")
    if interval_seconds is not None:
        if not spec.min_interval_seconds <= interval_seconds <= spec.max_interval_seconds:
            raise ValidationAuthError(
                (
                    f"La frequenza deve stare tra {spec.min_interval_seconds} e "
                    f"{spec.max_interval_seconds} secondi."
                ),
                code="system_job_interval_out_of_range",
            )
        row.interval_seconds = interval_seconds
    if enabled is not None:
        row.enabled = enabled
    session.flush()
    return _to_view(spec, row)


def beat_schedule_dict(session: Session) -> dict[str, dict[str, object]]:
    """Schedule Celery: solo i job accesi, con la frequenza salvata."""
    ensure_defaults(session)
    schedule: dict[str, dict[str, object]] = {}
    for row in session.scalars(select(SystemJob)).all():
        spec = SYSTEM_JOBS_BY_KEY.get(row.key)
        if spec is None or not row.enabled:
            continue
        entry: dict[str, object] = {
            "task": spec.task,
            "schedule": float(row.interval_seconds),
            "options": {"expires": float(row.interval_seconds)},
        }
        if spec.kwargs:
            entry["kwargs"] = dict(spec.kwargs)
        schedule[row.key] = entry
    return schedule


def allow_periodic(key: str, env_default: bool) -> bool:
    """True se il job deve girare. Una riga in tabella vince sull'ambiente.

    Se il database non risponde, resta il valore d'ambiente: un guasto di
    lettura non deve spegnere (né accendere a vuoto) i giri già configurati.
    """
    enabled = env_default
    try:
        settings = get_api_settings()
        engine = create_engine_from_url(settings.database_url)
        factory = create_session_factory(engine)
        try:
            with session_scope(factory) as session:
                row = session.get(SystemJob, key)
                if row is not None:
                    enabled = row.enabled
                if enabled:
                    _touch_started(session, key)
        finally:
            engine.dispose()
    except Exception:
        logger.exception("system_job_gate_failed", extra={"job_key": key})
        return env_default
    if not enabled:
        logger.info("system_job_skipped_disabled", extra={"job_key": key})
    return enabled


def _touch_started(session: Session, key: str) -> None:
    row = session.get(SystemJob, key)
    if row is None:
        return
    row.last_started_at = datetime.now(UTC)
    session.flush()


def _to_view(spec: SystemJobSpec, row: SystemJob) -> SystemJobView:
    next_run = None
    if row.enabled and row.last_started_at is not None:
        next_run = row.last_started_at + timedelta(seconds=row.interval_seconds)
    return SystemJobView(
        key=spec.key,
        title=spec.title,
        description=spec.description,
        task=spec.task,
        enabled=row.enabled,
        interval_seconds=row.interval_seconds,
        min_interval_seconds=spec.min_interval_seconds,
        max_interval_seconds=spec.max_interval_seconds,
        last_started_at=row.last_started_at,
        next_run_at=next_run,
    )


def _runtime_settings() -> object:
    """Il beat gira nel processo worker: lì ci sono anche i flag del sync stagionale."""
    try:
        from config.settings.loader import validate_worker_settings

        return validate_worker_settings()
    except Exception:
        return get_api_settings()


def _setting_bool(settings: object, attr: str, *, default: bool) -> bool:
    value = getattr(settings, attr, default)
    return bool(value)


def _setting_int(settings: object, attr: str, *, default: int) -> int:
    value = getattr(settings, attr, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
