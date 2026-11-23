"""Override operatore dei job periodici ed esito di ogni loro giro."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime


class SystemJob(Base, TimestampMixin):
    """Accensione e frequenza di un job del beat, modificabili dal pannello."""

    __tablename__ = "system_jobs"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    last_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class SystemJobRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Esito di un giro di un job periodico (release 1.4, «Da guardare» del Riepilogo).

    Scritto dal worker a fine giro (``system_jobs.run_recorder``): ``ok`` oppure ``failed``
    con il motivo. I giri saltati perché il job è spento non si scrivono. La tabella resta
    piccola: per ogni job si tengono gli ultimi giri e, più a lungo, quelli finiti con errore
    (``system_jobs.runs.prune_runs``).
    """

    __tablename__ = "system_job_runs"
    __table_args__ = (
        CheckConstraint("outcome IN ('ok', 'failed')", name="outcome"),
        Index("ix_system_job_runs_job_key_started_at", "job_key", "started_at"),
        Index("ix_system_job_runs_outcome_started_at", "outcome", "started_at"),
    )

    job_key: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Motivo dell'errore, in breve (codice o messaggio dell'eccezione). Vuoto se ``ok``.
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
