"""Giro delle formazioni probabili: parte da solo ogni ora e costa una chiamata al giorno.

Il 28/11 il giro a ora fissa (crontab 07:00 UTC) non è partito: lo scheduler del
pannello (``SystemJobScheduler``) riscrive ogni voce del beat come intervallo con la
frequenza salvata, e il crontab diventava "ogni 24 ore dall'avvio del beat". Qui si
prova lo scheduler vero di Celery in memoria e si contano le chiamate al fornitore
di un giro orario contro quelle del vecchio giro giornaliero. Nessuna rete.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from celery import Celery
from celery.schedules import crontab

from config.settings.worker import WorkerSettings
from sports_data.predicted import sync as sync_module
from sports_data.predicted.parse import ParsedLineup, ParsedMatchRef
from sports_data.predicted.sync import snapshot_min_age, sync_predicted_lineups
from sports_data.schedule import sports_data_beat_schedule
from system_jobs.catalog import SYSTEM_JOBS_BY_KEY
from system_jobs.models import SystemJob
from system_jobs.service import _to_view

_KEY = "sports-predicted-lineups"


# ---------------------------------------------------------------------------
# Schedule del beat e scheduler del pannello
# ---------------------------------------------------------------------------


def test_beat_schedules_are_intervals() -> None:
    """Lo scheduler del pannello sa fare solo intervalli: nessun crontab nel beat."""
    from fantasy_lineups.schedule import ai_lineups_beat_schedule
    from fantasy_turns.schedule import fantasy_turns_beat_schedule
    from notifications.schedule import notifications_beat_schedule
    from sports_data.scheduler.policy import beat_schedule_entries

    entries: dict[str, dict] = {}
    entries.update(beat_schedule_entries(enabled=True))
    entries.update(fantasy_turns_beat_schedule(enabled=True))
    entries.update(ai_lineups_beat_schedule(enabled=True))
    entries.update(
        notifications_beat_schedule(
            enabled=True,
            broadcast_enabled=True,
            lock_reminder_enabled=True,
            trade_expiry_enabled=True,
        )
    )
    for interval in (3600, 86_400):
        entries.update(
            sports_data_beat_schedule(
                catalog_enabled=True,
                fixtures_enabled=True,
                predicted_lineups_enabled=True,
                predicted_lineups_interval_seconds=interval,
                market_values_enabled=True,
            )
        )
        not_intervals = {
            key: spec["schedule"]
            for key, spec in entries.items()
            if not isinstance(spec["schedule"], int | float)
        }
        assert not_intervals == {}


def test_defaults_agree_on_an_hourly_check() -> None:
    beat = sports_data_beat_schedule(catalog_enabled=False, fixtures_enabled=False)
    assert beat[_KEY]["schedule"] == 3600.0
    assert beat[_KEY]["options"] == {"expires": 3600.0}
    assert SYSTEM_JOBS_BY_KEY[_KEY].default_interval_seconds == 3600
    fields = WorkerSettings.model_fields
    assert fields["predicted_lineups_interval_seconds"].default == 3600
    assert fields["predicted_lineups_daily_refresh_hour_utc"].default == 7


def _scheduler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    beat_entry: dict,
    saved_interval: float,
):  # type: ignore[no-untyped-def]
    """Lo ``SystemJobScheduler`` vero, con la tabella ``system_jobs`` finta."""
    import system_jobs.scheduler as scheduler_module

    desired = {
        _KEY: {
            "task": "sports_data.sync_predicted_lineups",
            "schedule": saved_interval,
            "options": {"expires": saved_interval},
        }
    }
    monkeypatch.setattr(
        scheduler_module,
        "get_api_settings",
        lambda: SimpleNamespace(database_url="postgresql://finto"),
    )
    monkeypatch.setattr(
        scheduler_module,
        "create_engine_from_url",
        lambda _url: SimpleNamespace(dispose=lambda: None),
    )
    monkeypatch.setattr(scheduler_module, "create_session_factory", lambda _engine: None)
    monkeypatch.setattr(
        scheduler_module, "session_scope", lambda _factory: contextlib.nullcontext(None)
    )
    monkeypatch.setattr(scheduler_module, "beat_schedule_dict", lambda _session: desired)
    app = Celery("prova-beat")
    app.conf.beat_schedule = {_KEY: beat_entry}
    return scheduler_module.SystemJobScheduler(
        app=app, schedule_filename=str(tmp_path / "beat"), lazy=False
    )


def test_cause_a_crontab_entry_becomes_every_24h_from_beat_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """La causa del 28/11: il crontab delle 07:00 non arriva mai al beat."""
    scheduler = _scheduler(
        monkeypatch,
        tmp_path,
        beat_entry={
            "task": "sports_data.sync_predicted_lineups",
            "schedule": crontab(hour=7, minute=0),
            "options": {"expires": 86_400.0},
        },
        saved_interval=86_400.0,
    )
    try:
        entry = scheduler.schedule[_KEY]
        assert not isinstance(entry.schedule, crontab)
        assert entry.schedule.run_every == timedelta(days=1)
        # Ultimo invio il 27/11 alle 11:30: alle 07:00:30 del 28/11 non è dovuto,
        # mentre il crontab da solo lo sarebbe stato.
        last = datetime(2026, 11, 27, 11, 30, tzinfo=UTC)
        at_seven = datetime(2026, 11, 28, 7, 0, 30, tzinfo=UTC)
        entry.schedule.nowfun = lambda: at_seven
        assert entry.schedule.is_due(last).is_due is False
        assert crontab(hour=7, minute=0, nowfun=lambda: at_seven).is_due(last).is_due
    finally:
        scheduler.schedule[_KEY].schedule.nowfun = None
        scheduler.close()


def test_hourly_entry_survives_the_operator_scheduler_and_comes_due(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    beat = sports_data_beat_schedule(catalog_enabled=False, fixtures_enabled=False)
    scheduler = _scheduler(monkeypatch, tmp_path, beat_entry=beat[_KEY], saved_interval=3600.0)
    try:
        entry = scheduler.schedule[_KEY]
        assert entry.schedule.run_every == timedelta(hours=1)
        assert entry.options == {"expires": 3600.0}
        # Beat (ri)avviato alle 07:20 del 28/11: il giro parte alle 08:20, non il 29.
        started = datetime(2026, 11, 28, 7, 20, tzinfo=UTC)
        entry.schedule.nowfun = lambda: started + timedelta(minutes=59)
        assert entry.schedule.is_due(started).is_due is False
        entry.schedule.nowfun = lambda: started + timedelta(hours=1, seconds=1)
        assert entry.schedule.is_due(started).is_due is True
    finally:
        scheduler.schedule[_KEY].schedule.nowfun = None
        scheduler.close()


def test_panel_next_run_is_last_start_plus_one_hour() -> None:
    spec = SYSTEM_JOBS_BY_KEY[_KEY]
    started = datetime(2026, 11, 28, 7, 20, tzinfo=UTC)
    row = SystemJob(key=_KEY, enabled=True, interval_seconds=3600, last_started_at=started)
    assert _to_view(spec, row).next_run_at == started + timedelta(hours=1)
    never = SystemJob(key=_KEY, enabled=True, interval_seconds=3600, last_started_at=None)
    assert _to_view(spec, never).next_run_at is None


def test_migration_moves_only_the_old_daily_default() -> None:
    migration = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "a4d7c2e9f610_predicted_lineups_hourly.py"
    ).read_text(encoding="utf-8")
    assert "SET interval_seconds = 3600" in migration
    assert "AND interval_seconds = 86400" in migration


# ---------------------------------------------------------------------------
# Guardia per partita: il mattino come scadenza dello snapshot
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 11, 28, 7, 0, tzinfo=UTC), timedelta(0)),
        (datetime(2026, 11, 28, 7, 40, tzinfo=UTC), timedelta(minutes=40)),
        (datetime(2026, 11, 28, 23, 0, tzinfo=UTC), timedelta(hours=16)),
        (datetime(2026, 11, 29, 6, 59, tzinfo=UTC), timedelta(hours=23, minutes=59)),
    ],
)
def test_snapshot_min_age_runs_back_to_the_last_morning(now: datetime, expected: timedelta) -> None:
    assert snapshot_min_age(now, min_age_hours=20, daily_refresh_hour_utc=7) == expected


def test_snapshot_min_age_without_morning_hour_is_the_fixed_age() -> None:
    now = datetime(2026, 11, 28, 9, 0, tzinfo=UTC)
    assert snapshot_min_age(now, min_age_hours=20, daily_refresh_hour_utc=None) == timedelta(
        hours=20
    )


def test_empty_morning_hour_env_means_fixed_age(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREDICTED_LINEUPS_DAILY_REFRESH_HOUR_UTC", "")
    assert WorkerSettings().predicted_lineups_daily_refresh_hour_utc is None


# ---------------------------------------------------------------------------
# Conteggio delle chiamate al fornitore: giro orario contro giro giornaliero
# ---------------------------------------------------------------------------


class _FakeFotmob:
    """Un client per giro, come quello vero: conta le richieste."""

    def __init__(self, world: _World) -> None:
        self._world = world
        self.requests_made = 0

    def matches_by_date(self, day: str) -> object:
        self.requests_made += 1
        self._world.calls.append(("by_date", day))
        return day

    def lineups(self, match_id: int) -> object:
        self.requests_made += 1
        self._world.calls.append(("lineups", match_id))
        return match_id


class _FakeSession:
    """Solo ciò che usa il ramo FotMob di ``sync_predicted_lineups``."""

    def __init__(self, world: _World) -> None:
        self._world = world

    def scalar(self, stmt: object) -> object:
        clause = stmt.whereclause  # type: ignore[attr-defined]
        if clause.left.key == "fixture_id":
            return self._world.links.get(clause.right.value)
        return None  # match FotMob non ancora preso da un'altra partita

    def add(self, row: object) -> None:
        self._world.links[row.fixture_id] = row  # type: ignore[attr-defined]

    def flush(self) -> None:
        return None


_CLUBS = (
    ("Juventus", "Lazio"),
    ("Arsenal", "Chelsea"),
    ("Barcelona", "Sevilla"),
    ("Bayern", "Dortmund"),
    ("Lille", "Nantes"),
)
#: Beat (ri)partito alle 09:17 UTC: un orario qualunque, come dopo un deploy.
_START = datetime(2026, 11, 28, 9, 17, tzinfo=UTC)


class _World:
    """5 partite su 3 date (29/11, 30/11, 1/12), tutte trovate da FotMob per data."""

    def __init__(self, *, unmatched: bool = False) -> None:
        self.calls: list[tuple[str, object]] = []
        self.links: dict[object, object] = {}
        self.snapshots: dict[object, datetime] = {}
        kickoff_days = [_START + timedelta(days=d) for d in (1, 1, 2, 2, 3)]
        clubs = list(_CLUBS)
        if unmatched:
            # Una partita che FotMob non elenca sotto quei nomi: mai collegata.
            kickoff_days.append(_START + timedelta(days=2))
            clubs.append(("Roma", "Napoli"))
        self.fixtures = [
            SimpleNamespace(
                id=uuid4(),
                provider_id=1000 + index,
                kickoff_at=day.replace(hour=19, minute=45),
                home_club=SimpleNamespace(name=home),
                away_club=SimpleNamespace(name=away),
            )
            for index, (day, (home, away)) in enumerate(zip(kickoff_days, clubs, strict=True))
        ]
        self.by_date: dict[str, tuple[ParsedMatchRef, ...]] = {}
        for index, fixture in enumerate(self.fixtures[: len(_CLUBS)]):
            day = fixture.kickoff_at.strftime("%Y%m%d")
            self.by_date[day] = (
                *self.by_date.get(day, ()),
                ParsedMatchRef(
                    fotmob_match_id=5000 + index,
                    home_name=fixture.home_club.name,
                    away_name=fixture.away_club.name,
                ),
            )

    def count(self, kind: str) -> int:
        return sum(1 for call_kind, _ in self.calls if call_kind == kind)


def _install(monkeypatch: pytest.MonkeyPatch, world: _World) -> None:
    def candidates(_session, *, now, horizon, league_id):  # type: ignore[no-untyped-def]
        # Come la query vera: partite non ancora iniziate entro l'orizzonte (4 giorni).
        return [f for f in world.fixtures if now < f.kickoff_at <= now + horizon]

    monkeypatch.setattr(sync_module, "_candidate_fixtures", candidates)
    monkeypatch.setattr(
        sync_module,
        "_has_recent_snapshot",
        lambda _s, fixture_id, cutoff: (
            fixture_id in world.snapshots and world.snapshots[fixture_id] >= cutoff
        ),
    )
    monkeypatch.setattr(
        sync_module, "parse_matches_by_date", lambda day: world.by_date.get(day, ())
    )
    monkeypatch.setattr(
        sync_module,
        "parse_lineup_payload",
        lambda _payload: ParsedLineup("predicted", None, None, None),
    )

    def store(_session, fixture, _match_id, _parsed, summary, now) -> None:  # type: ignore[no-untyped-def]
        world.snapshots[fixture.id] = now
        summary.snapshots_saved += 1

    monkeypatch.setattr(sync_module, "_store_snapshot", store)


def _run(world: _World, now: datetime, *, daily_hour: int | None, min_age_hours: int = 20) -> None:
    sync_predicted_lineups(
        _FakeSession(world),  # type: ignore[arg-type]
        _FakeFotmob(world),  # type: ignore[arg-type]
        now=now,
        min_age=snapshot_min_age(
            now, min_age_hours=min_age_hours, daily_refresh_hour_utc=daily_hour
        ),
    )


def _simulate(
    monkeypatch: pytest.MonkeyPatch,
    *,
    step: timedelta,
    daily_hour: int | None,
    unmatched: bool = False,
) -> tuple[_World, dict[object, list[datetime]]]:
    """Giri ogni ``step`` dal 28/11 09:17 finché tutte le partite sono iniziate."""
    world = _World(unmatched=unmatched)
    _install(monkeypatch, world)
    fetched: dict[object, list[datetime]] = {f.id: [] for f in world.fixtures}
    moment = _START
    while moment < max(f.kickoff_at for f in world.fixtures):
        before = dict(world.snapshots)
        _run(world, moment, daily_hour=daily_hour)
        for fixture_id, when in world.snapshots.items():
            if before.get(fixture_id) != when:
                fetched[fixture_id].append(when)
        moment += step
    return world, fetched


def test_hourly_run_costs_the_same_as_the_old_daily_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stesse chiamate del vecchio giro ogni 24 ore: 3 per data al primo giro, poi una
    formazione per partita al giorno (2+2+3+3+4 = 14)."""
    old_daily, _ = _simulate(monkeypatch, step=timedelta(days=1), daily_hour=None)
    hourly, fetched = _simulate(monkeypatch, step=timedelta(hours=1), daily_hour=7)
    assert (old_daily.count("by_date"), old_daily.count("lineups")) == (3, 14)
    assert (hourly.count("by_date"), hourly.count("lineups")) == (3, 14)
    # Dopo il primo giro, ogni partita si riscarica una volta al giorno, alle 07:xx UTC,
    # e l'ultima lettura è la mattina stessa della partita (dopo Soccer-Oracle delle 06:30).
    for fixture in hourly.fixtures:
        times = fetched[fixture.id]
        assert times[0] == _START
        assert all(t.hour == 7 for t in times[1:])
        assert times[-1].date() == fixture.kickoff_at.date()


def test_hourly_run_with_only_the_fixed_20h_age_reads_too_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Perché non basta la sola guardia a 20 ore: ogni partita torna ogni 21 ore circa,
    a orari che scivolano, e l'ultima lettura prima della partita può cadere di notte,
    prima dell'aggiornamento del mattino."""
    world, fetched = _simulate(monkeypatch, step=timedelta(hours=1), daily_hour=None)
    assert any(
        not (times[-1].date() == fixture.kickoff_at.date() and times[-1].hour >= 7)
        for fixture in world.fixtures
        for times in [fetched[fixture.id]]
    )


def test_beat_restarted_after_seven_catches_up_at_the_next_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Il caso del crontab: beat ripartito alle 07:40, il giro delle 08:40 aggiorna tutto."""
    world = _World()
    _install(monkeypatch, world)
    yesterday = datetime(2026, 11, 28, 7, 5, tzinfo=UTC)
    _run(world, yesterday, daily_hour=7)
    calls_before = len(world.calls)
    _run(world, datetime(2026, 11, 29, 6, 40, tzinfo=UTC), daily_hour=7)
    assert len(world.calls) == calls_before  # prima delle 07:00: tutto ancora buono
    after_restart = datetime(2026, 11, 29, 8, 40, tzinfo=UTC)
    _run(world, after_restart, daily_hour=7)
    still_upcoming = [f for f in world.fixtures if f.kickoff_at > after_restart]
    assert all(world.snapshots[f.id] == after_restart for f in still_upcoming)
    assert world.count("lineups") - 5 == len(still_upcoming)


def test_unmatched_fixture_is_retried_every_hour_at_one_call_per_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Il costo del giro orario: una partita mai collegata a FotMob si riprova a ogni
    giro, una chiamata «per data» (condivisa tra le partite dello stesso giorno), cioè
    fino a 24 al giorno invece di 1. Le formazioni delle altre non cambiano."""
    hourly, _ = _simulate(monkeypatch, step=timedelta(hours=1), daily_hour=7, unmatched=True)
    old_daily, _ = _simulate(monkeypatch, step=timedelta(days=1), daily_hour=None, unmatched=True)
    unmatched = hourly.fixtures[-1]
    hourly_ticks = int((unmatched.kickoff_at - _START) / timedelta(hours=1)) + 1
    assert hourly.count("lineups") == old_daily.count("lineups") == 14
    assert old_daily.count("by_date") == 3 + 2  # 28/11 e 29/11: la data del 30/11 ritorna
    assert hourly.count("by_date") == 3 + hourly_ticks - 1
