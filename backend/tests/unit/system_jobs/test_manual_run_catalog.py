"""Catalogo e «Esegui» (release 1.5): ogni job si può lanciare a mano senza argomenti in più."""

from __future__ import annotations

import inspect

import pytest

from admin.turni_batch import BATCH_OPERATIONS
from system_jobs.catalog import SYSTEM_JOBS, SYSTEM_JOBS_BY_KEY
from system_jobs.manual import ManualRunResult
from system_jobs.running import RunningMarker


@pytest.mark.parametrize("spec", SYSTEM_JOBS, ids=lambda spec: spec.key)
def test_ogni_job_del_catalogo_parte_con_i_soli_kwargs_di_catalogo(spec) -> None:
    """«Esegui» manda ``spec.task`` con ``spec.kwargs``: nessun argomento obbligatorio in più.

    Un job che chiedesse argomenti (una lega, un turno…) non si potrebbe lanciare a mano in modo
    sicuro e non andrebbe esposto: questo test lo segnala prima.
    """
    from app.worker import celery_app

    task = celery_app.tasks[spec.task]
    inspect.signature(task.run).bind(**spec.kwargs)


def test_i_job_che_usano_la_quota_del_fornitore_sono_quelli_che_lo_chiamano() -> None:
    quota = {spec.key for spec in SYSTEM_JOBS if spec.uses_provider_quota}

    assert quota == {
        "sports-poll-live",
        "sports-poll-pre",
        "sports-poll-post",
        "sports-poll-late",
        "fantasy-turns-refresh-full-calendar",
        "sports-data-sync-catalog",
        "sports-data-sync-fixtures",
        "sports-predicted-lineups",
    }
    # «Medie e Valore di mercato» dice di non chiamare il fornitore.
    assert not SYSTEM_JOBS_BY_KEY["market-values-refresh"].uses_provider_quota
    assert "Non chiama il fornitore" in SYSTEM_JOBS_BY_KEY["market-values-refresh"].description


def test_i_job_che_mandano_avvisi_sono_segnati() -> None:
    notifying = {spec.key for spec in SYSTEM_JOBS if spec.sends_notifications}

    assert notifying == {
        "fantasy-turns-ensure-upcoming",
        "notifications-lineup-reminders",
        "notifications-lineup-lock-reminders",
        "market-trade-expiry",
        "notifications-broadcast-dispatch",
    }


def test_le_operazioni_di_esegui_tutti_nei_turni_puntano_a_job_che_esistono() -> None:
    for operation in BATCH_OPERATIONS:
        assert operation.job_keys
        for key in operation.job_keys:
            assert key in SYSTEM_JOBS_BY_KEY


def test_il_segno_in_esecuzione_si_rilegge_uguale_e_ignora_il_testo_rotto() -> None:
    marker = RunningMarker("task-1", True, "operatore-1", "2026-11-28T10:00:00+00:00")

    assert RunningMarker.from_json(marker.to_json()) == marker
    assert RunningMarker.from_json("non è json") is None
    assert RunningMarker.from_json('{"manual": true}') is None
    assert RunningMarker.from_json(None) is None


def test_il_risultato_del_lancio_porta_gli_stessi_campi_della_risposta() -> None:
    result = ManualRunResult(key="k", title="T", status="started", message="m", task_id="t")

    assert result.as_dict() == {
        "key": "k",
        "title": "T",
        "status": "started",
        "message": "m",
        "warning": None,
        "code": None,
        "taskId": "t",
    }
