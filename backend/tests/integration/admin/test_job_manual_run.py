"""«Esegui» e «Esegui tutti» nel pannello operatore › Job (release 1.5, richiesta di Rosario 28/11).

- solo operatore (``global:operate``): gli altri ricevono 403;
- «Esegui» manda al worker il task del catalogo con i suoi kwargs, registra chi e quando (audit) e
  non cambia accensione né frequenza;
- un job spento si lancia a mano con un avviso, una volta sola;
- doppio lancio: un job già in esecuzione (a mano o dal beat) non si rilancia (409);
- «Esegui tutti» lancia i job accesi, un errore o un job già in corso non ferma gli altri;
- nessuna chiamata al fornitore: il dispatcher è finto, oppure il task è un giro locale.
"""

from __future__ import annotations

import re
from uuid import UUID

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import LeagueAuditAction, PlatformRole
from database.session import create_session_factory
from leagues.models.league_audit_event import LeagueAuditEvent
from mail.capture import get_captured_emails
from system_jobs import manual as manual_module
from system_jobs import running
from system_jobs.catalog import SYSTEM_JOBS, SYSTEM_JOBS_BY_KEY
from system_jobs.models import SystemJob, SystemJobRun
from system_jobs.runs import record_run

PASSWORD = "Password123!"
FIXTURES_JOB = "sports-data-sync-fixtures"  # chiama il fornitore, ha kwargs di catalogo
BROADCAST_JOB = "notifications-broadcast-dispatch"  # giro locale: nessun fornitore


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(SystemJobRun))
        session.execute(delete(SystemJob))
        session.execute(
            delete(LeagueAuditEvent).where(
                LeagueAuditEvent.action == LeagueAuditAction.SYSTEM_JOB_RUN_MANUAL
            )
        )
        session.commit()
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _clean_running_markers(redis_url: str) -> None:
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    for key in client.scan_iter(f"{running.KEY_PREFIX}*"):
        client.delete(key)
    yield
    for key in client.scan_iter(f"{running.KEY_PREFIX}*"):
        client.delete(key)


class FakeDispatcher:
    """Al posto di Celery: registra i task che sarebbero partiti, senza eseguirli."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.fail_for: set[str] = set()

    def __call__(self, task_name: str, *, task_id: str, kwargs: dict[str, object]) -> None:
        if task_name in self.fail_for:
            raise ConnectionError("broker spento")
        self.calls.append((task_name, task_id, kwargs))


@pytest.fixture
def dispatcher(monkeypatch: pytest.MonkeyPatch) -> FakeDispatcher:
    fake = FakeDispatcher()
    monkeypatch.setattr(manual_module, "dispatch_task", fake)
    return fake


def _login(client: TestClient, db_session: Session, email: str, *, operator: bool):
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": email.split("@")[0]},
    )
    emails = get_captured_emails()
    if emails:
        match = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1].message.text_body)
        if match:
            client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    user_id = UUID(login.json()["user"]["id"])
    if operator:
        user = db_session.get(User, user_id)
        assert user is not None
        user.platform_role = PlatformRole.OPERATOR
        db_session.commit()
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}, user_id


def _set_enabled(db_session: Session, key: str, enabled: bool) -> None:
    from system_jobs.service import ensure_defaults

    ensure_defaults(db_session)
    row = db_session.get(SystemJob, key)
    assert row is not None
    row.enabled = enabled
    db_session.commit()


def _audit_rows(db_session: Session) -> list[LeagueAuditEvent]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(LeagueAuditEvent).where(
                LeagueAuditEvent.action == LeagueAuditAction.SYSTEM_JOB_RUN_MANUAL
            )
        ).all()
    )


# --- permessi -----------------------------------------------------------------------------------


def test_chi_non_e_operatore_riceve_403_su_esegui_e_esegui_tutti(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    member, _ = _login(client, db_session, "jobrun-member@example.com", operator=False)

    assert client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=member).status_code == 403
    assert client.post("/admin/job/esegui-tutti", headers=member).status_code == 403
    assert dispatcher.calls == []
    assert _audit_rows(db_session) == []


def test_senza_accesso_riceve_401(client: TestClient, dispatcher: FakeDispatcher) -> None:
    assert client.post(f"/admin/job/{FIXTURES_JOB}/esegui").status_code == 401
    assert client.post("/admin/job/esegui-tutti").status_code == 401
    assert dispatcher.calls == []


# --- «Esegui» su un job -------------------------------------------------------------------------


def test_esegui_manda_il_task_del_catalogo_e_registra_chi_lo_ha_lanciato(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, operator_id = _login(client, db_session, "jobrun-op1@example.com", operator=True)
    _set_enabled(db_session, FIXTURES_JOB, True)
    before = db_session.get(SystemJob, FIXTURES_JOB)
    interval_before = before.interval_seconds

    response = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["key"] == FIXTURES_JOB
    assert body["status"] == "started"
    assert body["warning"] is None
    assert "in coda" in body["message"]
    spec = SYSTEM_JOBS_BY_KEY[FIXTURES_JOB]
    # Lo stesso task e gli stessi kwargs del beat: il giro non cambia.
    assert dispatcher.calls == [(spec.task, body["taskId"], {"include_details": False})]
    # Il lancio prenota il job: finché non finisce, un secondo lancio è rifiutato.
    marker = running.read(FIXTURES_JOB)
    assert marker is not None
    assert marker.manual is True
    assert marker.task_id == body["taskId"]
    assert marker.actor_id == str(operator_id)
    # Chi, quando e quale job, nel registro di audit di piattaforma.
    rows = _audit_rows(db_session)
    assert len(rows) == 1
    assert rows[0].actor_id == operator_id
    assert rows[0].league_id is None
    assert rows[0].created_at is not None
    assert rows[0].details == {
        "operation": "system_job_manual_run",
        "jobKey": FIXTURES_JOB,
        "taskId": body["taskId"],
        "wasEnabled": True,
        "allJobs": False,
    }
    # Accensione e frequenza non si toccano.
    db_session.expire_all()
    after = db_session.get(SystemJob, FIXTURES_JOB)
    assert after.enabled is True
    assert after.interval_seconds == interval_before


def test_esegui_su_un_job_inesistente_da_404(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op2@example.com", operator=True)

    response = client.post("/admin/job/non-esiste/esegui", headers=operator)

    assert response.status_code == 404
    assert response.json()["code"] == "system_job_not_found"
    assert dispatcher.calls == []


def test_un_job_spento_si_lancia_a_mano_con_un_avviso(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op3@example.com", operator=True)
    _set_enabled(db_session, FIXTURES_JOB, False)

    response = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "started"
    assert "spento" in body["warning"]
    assert "una volta sola" in body["warning"]
    assert len(dispatcher.calls) == 1
    # Resta spento: il lancio a mano non lo riaccende.
    db_session.expire_all()
    assert db_session.get(SystemJob, FIXTURES_JOB).enabled is False
    assert _audit_rows(db_session)[0].details["wasEnabled"] is False


def test_il_doppio_lancio_e_rifiutato_finche_il_job_gira(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op4@example.com", operator=True)

    first = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)
    second = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "system_job_already_running"
    assert "già in esecuzione" in second.json()["message"]
    assert len(dispatcher.calls) == 1
    assert len(_audit_rows(db_session)) == 1
    # Finito il giro il segno si toglie e si può rilanciare.
    assert running.release(FIXTURES_JOB, first.json()["taskId"]) is True
    third = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)
    assert third.status_code == 200
    assert len(dispatcher.calls) == 2


def test_un_giro_del_beat_in_corso_blocca_il_lancio_a_mano(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op5@example.com", operator=True)
    # Il worker segna l'inizio di un giro del beat (task_prerun).
    running.mark_started_by_worker(FIXTURES_JOB, "beat-task-1")

    response = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)

    assert response.status_code == 409
    assert dispatcher.calls == []


def test_se_il_task_non_parte_il_job_si_libera_e_non_resta_in_audit(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op6@example.com", operator=True)
    dispatcher.fail_for.add(SYSTEM_JOBS_BY_KEY[FIXTURES_JOB].task)

    response = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)

    assert response.status_code == 502
    assert response.json()["code"] == "system_job_dispatch_failed"
    assert running.read(FIXTURES_JOB) is None
    assert _audit_rows(db_session) == []


def test_senza_redis_il_lancio_a_mano_e_rifiutato(
    client: TestClient,
    db_session: Session,
    dispatcher: FakeDispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op7@example.com", operator=True)

    def unavailable() -> redis.Redis:
        raise running.RunningUnavailableError("redis spento")

    monkeypatch.setattr(running, "_client", unavailable)

    response = client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)

    assert response.status_code == 503
    assert response.json()["code"] == "system_job_lock_unavailable"
    assert dispatcher.calls == []


# --- «Esegui tutti» -----------------------------------------------------------------------------


def test_esegui_tutti_lancia_i_job_accesi_e_salta_gli_spenti(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, operator_id = _login(client, db_session, "jobrun-op8@example.com", operator=True)
    _set_enabled(db_session, FIXTURES_JOB, False)
    off_task = SYSTEM_JOBS_BY_KEY[FIXTURES_JOB].task

    response = client.post("/admin/job/esegui-tutti", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    enabled_keys = [row.key for row in db_session.scalars(select(SystemJob)).all() if row.enabled]
    assert enabled_keys  # i default accesi del catalogo
    assert [result["key"] for result in body["results"]] == [
        spec.key for spec in SYSTEM_JOBS if spec.key in enabled_keys
    ]
    assert FIXTURES_JOB not in [result["key"] for result in body["results"]]
    assert {call[0] for call in dispatcher.calls}.isdisjoint({off_task})
    assert body["started"] == len(enabled_keys)
    assert body["alreadyRunning"] == 0
    assert body["failed"] == 0
    assert all(result["status"] == "started" for result in body["results"])
    assert all(result["warning"] is None for result in body["results"])
    rows = _audit_rows(db_session)
    assert len(rows) == len(enabled_keys)
    assert {row.actor_id for row in rows} == {operator_id}
    assert all(row.details["allJobs"] is True for row in rows)


def test_esegui_tutti_un_job_gia_in_corso_o_che_non_parte_non_ferma_gli_altri(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op9@example.com", operator=True)
    running_key = "sports-poll-live"
    failing_key = "market-values-refresh"
    _set_enabled(db_session, running_key, True)
    _set_enabled(db_session, failing_key, True)
    running.mark_started_by_worker(running_key, "beat-task-2")
    dispatcher.fail_for.add(SYSTEM_JOBS_BY_KEY[failing_key].task)

    response = client.post("/admin/job/esegui-tutti", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    by_key = {result["key"]: result for result in body["results"]}
    assert by_key[running_key]["status"] == "already_running"
    assert "già in esecuzione" in by_key[running_key]["message"]
    assert by_key[failing_key]["status"] == "failed"
    assert "non lanciato" in by_key[failing_key]["message"]
    others = [r for key, r in by_key.items() if key not in (running_key, failing_key)]
    assert others
    assert all(result["status"] == "started" for result in others)
    assert body["alreadyRunning"] == 1
    assert body["failed"] == 1
    assert body["started"] == len(others)
    # Il segno del job che non è partito si è liberato, quello del giro del beat è rimasto.
    assert running.read(failing_key) is None
    assert running.read(running_key) is not None
    assert len(_audit_rows(db_session)) == len(others)


def test_esegui_tutti_due_volte_di_fila_non_rilancia_nulla(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op10@example.com", operator=True)

    first = client.post("/admin/job/esegui-tutti", headers=operator).json()
    launched = len(dispatcher.calls)
    second = client.post("/admin/job/esegui-tutti", headers=operator).json()

    assert first["started"] == launched > 0
    assert second["started"] == 0
    assert second["alreadyRunning"] == launched
    assert len(dispatcher.calls) == launched


# --- elenco dei job ----------------------------------------------------------------------------


def test_l_elenco_dice_se_un_job_gira_la_quota_del_fornitore_e_l_ultimo_esito(
    client: TestClient, db_session: Session, dispatcher: FakeDispatcher
) -> None:
    operator, _ = _login(client, db_session, "jobrun-op11@example.com", operator=True)
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    record_run(
        db_session,
        job_key=BROADCAST_JOB,
        outcome="failed",
        reason="Qualcosa non va.",
        started_at=now,
        finished_at=now,
    )
    db_session.commit()
    client.post(f"/admin/job/{FIXTURES_JOB}/esegui", headers=operator)

    response = client.get("/admin/job", headers=operator)

    assert response.status_code == 200
    jobs = {job["key"]: job for job in response.json()}
    assert jobs[FIXTURES_JOB]["running"] is True
    assert jobs[FIXTURES_JOB]["usesProviderQuota"] is True
    assert jobs[FIXTURES_JOB]["lastRun"] is None
    assert jobs[BROADCAST_JOB]["running"] is False
    assert jobs[BROADCAST_JOB]["usesProviderQuota"] is False
    assert jobs[BROADCAST_JOB]["sendsNotifications"] is True
    assert jobs[BROADCAST_JOB]["lastRun"]["outcome"] == "failed"
    assert jobs[BROADCAST_JOB]["lastRun"]["reason"] == "Qualcosa non va."
    assert jobs["market-values-refresh"]["usesProviderQuota"] is False
    # I campi di prima restano (l'app 1.4 già installata legge solo quelli).
    assert {"key", "title", "description", "task", "enabled", "intervalSeconds"} <= set(
        jobs[FIXTURES_JOB]
    )


# --- dal lancio al giro vero (task locale, Celery eager) ----------------------------------------


def test_un_job_spento_lanciato_a_mano_gira_davvero_una_volta_e_poi_si_libera(
    client: TestClient, db_session: Session
) -> None:
    """Senza finto dispatcher: «Avvisi programmati» è un giro locale (nessun fornitore).

    Spento, il giro del beat si salta (nessun esito). Lanciato a mano passa, scrive il suo esito
    ``ok``, non tocca ``last_started_at`` e toglie il segno «in esecuzione» a fine giro.
    """
    operator, _ = _login(client, db_session, "jobrun-op12@example.com", operator=True)
    _set_enabled(db_session, BROADCAST_JOB, False)
    spec = SYSTEM_JOBS_BY_KEY[BROADCAST_JOB]

    # Giro del beat a job spento: saltato, niente esito.
    manual_module.dispatch_task(spec.task, task_id="beat-run-1", kwargs={})
    db_session.expire_all()
    assert (
        db_session.scalars(select(SystemJobRun).where(SystemJobRun.job_key == BROADCAST_JOB)).all()
        == []
    )

    response = client.post(f"/admin/job/{BROADCAST_JOB}/esegui", headers=operator)

    assert response.status_code == 200, response.text
    assert "spento" in response.json()["warning"]
    db_session.expire_all()
    runs = db_session.scalars(
        select(SystemJobRun).where(SystemJobRun.job_key == BROADCAST_JOB)
    ).all()
    assert [run.outcome for run in runs] == ["ok"]
    assert runs[0].task_id == response.json()["taskId"]
    row = db_session.get(SystemJob, BROADCAST_JOB)
    assert row.enabled is False
    assert row.last_started_at is None
    assert running.read(BROADCAST_JOB) is None
    # E si può rilanciare.
    again = client.post(f"/admin/job/{BROADCAST_JOB}/esegui", headers=operator)
    assert again.status_code == 200
