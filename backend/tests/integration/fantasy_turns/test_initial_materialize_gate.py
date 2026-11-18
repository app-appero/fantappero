"""QA 18/11: i turni iniziali di una lega nuova seguono l'interruttore del pannello.

Su dev la variabile d'ambiente teneva spenta la generazione automatica, ma
l'operatore aveva acceso il job "Turni in arrivo" dal pannello: il controllo
orario girava, i turni iniziali delle leghe nuove no.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from config.settings.loader import reset_settings_cache
from database.session import create_session_factory
from system_jobs.models import SystemJob
from system_jobs.service import is_job_enabled

JOB_KEY = "fantasy-turns-ensure-upcoming"


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.query(SystemJob).filter(SystemJob.key == JOB_KEY).delete()
        session.commit()
        session.close()
        engine.dispose()


def _set_job(session: Session, *, enabled: bool) -> None:
    row = session.get(SystemJob, JOB_KEY)
    if row is None:
        session.add(SystemJob(key=JOB_KEY, enabled=enabled, interval_seconds=3600))
    else:
        row.enabled = enabled
    session.commit()


def test_is_job_enabled_prefers_the_panel_over_the_environment(db_session: Session) -> None:
    reset_settings_cache()
    assert is_job_enabled(JOB_KEY, False) is False  # nessuna riga: vale l'ambiente
    _set_job(db_session, enabled=True)
    assert is_job_enabled(JOB_KEY, False) is True
    _set_job(db_session, enabled=False)
    assert is_job_enabled(JOB_KEY, True) is False


def test_initial_materialization_runs_when_the_panel_enables_the_job(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fantasy_turns.tasks as tasks

    monkeypatch.setenv("FANTASY_TURNS_AUTO_GENERATE_ENABLED", "false")
    reset_settings_cache()
    calls: list[object] = []

    class _Service:
        def __init__(self, _session: object) -> None:
            pass

        def materialize_full_season(self, league: object, **_kwargs: object) -> SimpleNamespace:
            calls.append(league)
            return SimpleNamespace(created=3, upgraded=0, opened=0, removed=0)

    monkeypatch.setattr(tasks, "FantasyTurnService", _Service)
    monkeypatch.setattr(
        tasks,
        "session_scope",
        _fake_scope(SimpleNamespace(get=lambda _model, _id: SimpleNamespace(id=_id))),
    )

    skipped = tasks.materialize_initial_fantasy_turns_task(league_id=str(uuid4()), actor_id=None)
    assert skipped == {"created": 0, "upgraded": 0, "opened": 0, "removed": 0}
    assert calls == []

    _set_job(db_session, enabled=True)
    done = tasks.materialize_initial_fantasy_turns_task(league_id=str(uuid4()), actor_id=None)
    assert done["created"] == 3
    assert len(calls) == 1
    reset_settings_cache()


def _fake_scope(session: object):
    from contextlib import contextmanager

    @contextmanager
    def scope(_factory: object):
        yield session

    return scope
