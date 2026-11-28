"""«Esegui tutti» nel pannello operatore › Turni (release 1.5, richiesta di Rosario 28/11).

- solo operatore (``global:operate``): gli altri ricevono 403;
- lancia le cinque operazioni sicure da rilanciare, in ordine, e per ognuna lascia l'esito;
- un errore non ferma le altre; un job automatico già in corso fa saltare l'operazione gemella;
- un solo blocco alla volta (409);
- chi e quando nel registro di audit; nessuna chiamata al fornitore (operazioni finte).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from uuid import UUID

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from admin import turni_batch
from auth.models.user import User
from database.enums import LeagueAuditAction, PlatformRole
from database.session import create_session_factory
from leagues.models.league_audit_event import LeagueAuditEvent
from mail.capture import get_captured_emails
from sports_data.provider.errors import ProviderRateLimitError
from system_jobs import running

PASSWORD = "Password123!"
EXPECTED_ORDER = [
    "importa-stagione",
    "genera-calendario",
    "sincronizza-turni",
    "formazioni-probabili",
    "formazioni-ia",
]


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(
            delete(LeagueAuditEvent).where(
                LeagueAuditEvent.action == LeagueAuditAction.SYSTEM_JOB_RUN_MANUAL
            )
        )
        session.commit()
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _clean_redis(redis_url: str) -> None:
    client = redis.Redis.from_url(redis_url, decode_responses=True)

    def wipe() -> None:
        for pattern in (f"{running.KEY_PREFIX}*", "fantappero:admin:turni_batch:*"):
            for key in client.scan_iter(pattern):
                client.delete(key)

    wipe()
    yield
    wipe()


class FakeRunners:
    """Sostituisce le operazioni vere: registra l'ordine e non chiama nessun fornitore."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.called: list[str] = []
        self.actors: list[str] = []
        self._monkeypatch = monkeypatch
        for key in EXPECTED_ORDER:
            self.set(key, lambda actor, key=key: f"{key}: fatto.")

    def set(self, key: str, runner: Callable[[str], str]) -> None:
        def wrapped(actor_id: str) -> str:
            self.called.append(key)
            self.actors.append(actor_id)
            return runner(actor_id)

        self._monkeypatch.setitem(turni_batch.OPERATION_RUNNERS, key, wrapped)


@pytest.fixture
def runners(monkeypatch: pytest.MonkeyPatch) -> FakeRunners:
    return FakeRunners(monkeypatch)


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


def _audit_rows(db_session: Session) -> list[LeagueAuditEvent]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(LeagueAuditEvent).where(
                LeagueAuditEvent.action == LeagueAuditAction.SYSTEM_JOB_RUN_MANUAL
            )
        ).all()
    )


def test_chi_non_e_operatore_riceve_403(
    client: TestClient, db_session: Session, runners: FakeRunners
) -> None:
    member, _ = _login(client, db_session, "turnibatch-member@example.com", operator=False)

    assert client.post("/admin/turni/esegui-tutti", headers=member).status_code == 403
    assert client.get("/admin/turni/esegui-tutti/qualcosa", headers=member).status_code == 403
    assert runners.called == []
    assert _audit_rows(db_session) == []


def test_senza_accesso_riceve_401(client: TestClient, runners: FakeRunners) -> None:
    assert client.post("/admin/turni/esegui-tutti").status_code == 401
    assert runners.called == []


def test_le_operazioni_sono_quelle_sicure_e_non_ce_nulla_a_senso_unico() -> None:
    assert [spec.key for spec in turni_batch.BATCH_OPERATIONS] == EXPECTED_ORDER
    assert set(turni_batch.OPERATION_RUNNERS) == set(EXPECTED_ORDER)
    labels = " | ".join(spec.label for spec in turni_batch.BATCH_OPERATIONS).lower()
    # Omologazioni, ricalcolo dello storico e recupero risultati restano ai pulsanti singoli.
    for excluded in ("calcola giornata", "recupera", "ricalcola", "omologa"):
        assert excluded not in labels


def test_esegui_tutti_lancia_le_operazioni_in_ordine_e_dice_l_esito_di_ognuna(
    client: TestClient, db_session: Session, runners: FakeRunners
) -> None:
    operator, operator_id = _login(client, db_session, "turnibatch-op1@example.com", operator=True)

    response = client.post("/admin/turni/esegui-tutti", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert [op["key"] for op in body["operations"]] == EXPECTED_ORDER
    assert runners.called == EXPECTED_ORDER
    assert set(runners.actors) == {str(operator_id)}
    assert [op["status"] for op in body["operations"]] == ["ok"] * 5
    assert body["operations"][0]["label"] == "Importa calendario stagione"
    assert body["operations"][0]["message"] == "importa-stagione: fatto."
    assert (body["ok"], body["failed"], body["skipped"]) == (5, 0, 0)
    assert body["startedAt"] and body["finishedAt"]
    # Lo stesso avanzamento si rilegge dal GET.
    again = client.get(f"/admin/turni/esegui-tutti/{body['batchId']}", headers=operator)
    assert again.status_code == 200
    assert again.json() == body
    # Chi e quando.
    rows = _audit_rows(db_session)
    assert len(rows) == 1
    assert rows[0].actor_id == operator_id
    assert rows[0].league_id is None
    assert rows[0].details == {
        "operation": "turni_batch_manual_run",
        "batchId": body["batchId"],
        "operations": EXPECTED_ORDER,
    }


def test_un_errore_non_ferma_le_altre_operazioni(
    client: TestClient, db_session: Session, runners: FakeRunners
) -> None:
    operator, _ = _login(client, db_session, "turnibatch-op2@example.com", operator=True)

    def rate_limited(_actor: str) -> str:
        raise ProviderRateLimitError("429")

    def broken(_actor: str) -> str:
        raise turni_batch.OperationFailedError("Leghe attive: 3, aggiornate: 2, fallite: 1.")

    def boom(_actor: str) -> str:
        raise RuntimeError("qualcosa si è rotto")

    runners.set("importa-stagione", rate_limited)
    runners.set("genera-calendario", broken)
    runners.set("formazioni-probabili", boom)

    response = client.post("/admin/turni/esegui-tutti", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert runners.called == EXPECTED_ORDER  # tutte tentate, nell'ordine
    by_key = {op["key"]: op for op in body["operations"]}
    assert by_key["importa-stagione"]["status"] == "failed"
    assert "troppe richieste" in by_key["importa-stagione"]["message"]
    assert by_key["genera-calendario"]["status"] == "failed"
    assert by_key["genera-calendario"]["message"] == "Leghe attive: 3, aggiornate: 2, fallite: 1."
    assert by_key["sincronizza-turni"]["status"] == "ok"
    assert by_key["formazioni-probabili"]["status"] == "failed"
    assert "RuntimeError" in by_key["formazioni-probabili"]["message"]
    assert by_key["formazioni-ia"]["status"] == "ok"
    assert (body["ok"], body["failed"], body["skipped"]) == (2, 3, 0)


def test_un_job_automatico_gia_in_corso_fa_saltare_l_operazione_gemella(
    client: TestClient, db_session: Session, runners: FakeRunners
) -> None:
    operator, _ = _login(client, db_session, "turnibatch-op3@example.com", operator=True)
    running.mark_started_by_worker("sports-predicted-lineups", "beat-task-3")

    response = client.post("/admin/turni/esegui-tutti", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    by_key = {op["key"]: op for op in body["operations"]}
    assert by_key["formazioni-probabili"]["status"] == "skipped"
    assert "già in esecuzione" in by_key["formazioni-probabili"]["message"]
    assert "formazioni-probabili" not in runners.called
    assert (body["ok"], body["failed"], body["skipped"]) == (4, 0, 1)
    # Il giro del beat non è stato toccato e le altre operazioni hanno liberato i loro job.
    marker = running.read("sports-predicted-lineups")
    assert marker is not None and marker.task_id == "beat-task-3"
    assert running.read("sports-data-sync-catalog") is None
    assert running.read("fantasy-turns-ensure-upcoming") is None


def test_un_solo_blocco_alla_volta(
    client: TestClient, db_session: Session, runners: FakeRunners
) -> None:
    operator, _ = _login(client, db_session, "turnibatch-op4@example.com", operator=True)
    assert turni_batch.acquire_lock("altro-blocco") is True

    refused = client.post("/admin/turni/esegui-tutti", headers=operator)

    assert refused.status_code == 409
    assert refused.json()["code"] == "turni_batch_already_running"
    assert "già in corso" in refused.json()["message"]
    assert runners.called == []
    assert _audit_rows(db_session) == []
    # Finito l'altro blocco, si può lanciare.
    turni_batch.release_lock("altro-blocco")
    accepted = client.post("/admin/turni/esegui-tutti", headers=operator)
    assert accepted.status_code == 200
    # A fine blocco il blocco Redis è libero: un secondo «Esegui tutti» parte.
    again = client.post("/admin/turni/esegui-tutti", headers=operator)
    assert again.status_code == 200
    assert runners.called == EXPECTED_ORDER * 2


def test_se_il_task_non_si_mette_in_coda_il_blocco_si_libera(
    client: TestClient,
    db_session: Session,
    runners: FakeRunners,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operator, _ = _login(client, db_session, "turnibatch-op5@example.com", operator=True)
    from admin.turni_batch_tasks import run_turni_batch_task

    def broker_down(*_args: object, **_kwargs: object) -> None:
        raise ConnectionError("broker spento")

    monkeypatch.setattr(run_turni_batch_task, "apply_async", broker_down)

    response = client.post("/admin/turni/esegui-tutti", headers=operator)

    assert response.status_code == 502
    assert response.json()["code"] == "turni_batch_dispatch_failed"
    assert turni_batch.acquire_lock("subito-dopo") is True


def test_senza_redis_il_blocco_non_parte(
    client: TestClient,
    db_session: Session,
    runners: FakeRunners,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operator, _ = _login(client, db_session, "turnibatch-op6@example.com", operator=True)

    def unavailable() -> redis.Redis:
        raise turni_batch.BatchUnavailableError("redis spento")

    monkeypatch.setattr(turni_batch, "_client", unavailable)

    response = client.post("/admin/turni/esegui-tutti", headers=operator)

    assert response.status_code == 503
    assert response.json()["code"] == "turni_batch_lock_unavailable"
    assert runners.called == []


def test_un_blocco_sconosciuto_da_404(
    client: TestClient, db_session: Session, runners: FakeRunners
) -> None:
    operator, _ = _login(client, db_session, "turnibatch-op7@example.com", operator=True)

    response = client.get("/admin/turni/esegui-tutti/non-esiste", headers=operator)

    assert response.status_code == 404
    assert response.json()["code"] == "turni_batch_not_found"


# --- le operazioni vere, senza fornitore --------------------------------------------------------


def test_sincronizza_turni_e_formazioni_ia_girano_sul_database_senza_fornitore(
    db_session: Session,
) -> None:
    sync = turni_batch._run_sync_turns("op")
    ai = turni_batch._run_ai_lineups("op")

    assert sync.startswith("Leghe: ")
    assert "Turni creati:" in sync and "aperti:" in sync and "in attesa:" in sync
    assert ai.startswith("Turni processati: ")
    assert "Squadre aggiornate:" in ai and "invariate:" in ai


def test_aggiorna_probabili_usa_il_giro_manuale_forzato(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_sync(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {"snapshots_saved": 4, "skipped_unmatched": 1, "message": None}

    monkeypatch.setattr("sports_data.predicted.tasks.run_predicted_lineup_sync", fake_sync)

    message = turni_batch._run_predicted_lineups("op")

    assert seen == {"force": True, "manual": True}
    assert message == "Formazioni probabili aggiornate: 4 salvate, 1 senza corrispondenza."


@pytest.mark.parametrize(
    ("runner_name", "task_path"),
    [
        ("_run_import_season", "sports_data.season_import_tasks.import_season_task"),
        (
            "_run_generate_calendar",
            "fantasy_turns.tasks.refresh_full_calendar_active_leagues_now_task",
        ),
    ],
)
def test_import_stagione_e_genera_calendario_chiamano_il_task_con_job_e_operatore(
    monkeypatch: pytest.MonkeyPatch, runner_name: str, task_path: str
) -> None:
    from fantasy_turns.calendar_refresh_progress import CalendarRefreshProgress, save_progress

    seen: dict[str, object] = {}

    def fake_task(*, job_id: str, actor_id: str | None) -> dict[str, object]:
        seen.update(job_id=job_id, actor_id=actor_id)
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id="platform",
                status="completed",
                percent=100,
                stage="completed",
                message="Fatto dal task finto.",
                result={},
            )
        )
        return {"status": "completed"}

    monkeypatch.setattr(task_path, fake_task)

    message = getattr(turni_batch, runner_name)("operatore-1")

    assert message == "Fatto dal task finto."
    assert seen["actor_id"] == "operatore-1"
    assert seen["job_id"]


def test_i_messaggi_dei_giri_con_avanzamento(monkeypatch: pytest.MonkeyPatch) -> None:
    from fantasy_turns.calendar_refresh_progress import CalendarRefreshProgress, save_progress

    def store(job_id: str, *, status: str, message: str, result: dict | None = None) -> None:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id="platform",
                status=status,
                percent=100,
                stage=status,
                message=message,
                result=result,
            )
        )

    store("ok-1", status="completed", message="Tutto aggiornato.", result={"failed": 0})
    store("ko-1", status="failed", message="Quota del fornitore finita.")
    store("part-1", status="completed", message="Aggiornate 2 leghe su 3.", result={"failed": 1})

    assert turni_batch._progress_message("ok-1", {}) == "Tutto aggiornato."
    with pytest.raises(turni_batch.OperationFailedError, match="Quota del fornitore finita"):
        turni_batch._progress_message("ko-1", {})
    with pytest.raises(turni_batch.OperationFailedError, match="2 leghe su 3"):
        turni_batch._progress_message("part-1", {})
    with pytest.raises(turni_batch.OperationFailedError, match="provider_rate_limited"):
        turni_batch._progress_message(
            "senza-avanzamento", {"status": "failed", "code": "provider_rate_limited"}
        )
