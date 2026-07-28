"""Correlation ID create/propagate between HTTP and Celery headers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from observability.celery_signals import _on_task_prerun
from observability.constants import CORRELATION_ID_HEADER, REQUEST_ID_HEADER
from observability.context import clear_context, get_correlation_id, get_job_id
from observability.propagation import (
    celery_task_headers,
    correlation_from_celery_headers,
    ensure_correlation_id,
)

client = TestClient(app)


def setup_function() -> None:
    clear_context()


def test_api_generates_correlation_id_when_absent() -> None:
    response = client.get("/")
    assert response.status_code == 200
    corr = response.headers.get(CORRELATION_ID_HEADER)
    assert corr
    assert len(corr) >= 32


def test_api_propagates_inbound_correlation_id() -> None:
    inbound = "11111111-2222-3333-4444-555555555555"
    response = client.get("/", headers={CORRELATION_ID_HEADER: inbound})
    assert response.headers.get(CORRELATION_ID_HEADER) == inbound
    assert response.headers.get(REQUEST_ID_HEADER)


def test_api_uses_request_id_as_correlation_fallback() -> None:
    inbound = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    response = client.get("/", headers={REQUEST_ID_HEADER: inbound})
    assert response.headers.get(CORRELATION_ID_HEADER) == inbound


def test_celery_headers_carry_api_correlation() -> None:
    corr = ensure_correlation_id("corr-from-api")
    headers = celery_task_headers(correlation_id=corr, request_id="req-1")
    assert headers["correlation_id"] == "corr-from-api"
    assert headers["request_id"] == "req-1"
    assert correlation_from_celery_headers(headers) == "corr-from-api"


def test_worker_signal_binds_correlation_and_job_id() -> None:
    class _Request:
        headers = {"correlation_id": "worker-corr-99", "request_id": "worker-req-99"}

    class _Task:
        name = "app.worker.ping"
        request = _Request()

    _on_task_prerun(sender=_Task, task_id="job-abc", task=_Task())
    assert get_correlation_id() == "worker-corr-99"
    assert get_job_id() == "job-abc"


def test_middleware_on_isolated_app() -> None:
    from observability.middleware import install_correlation_middleware

    isolated = FastAPI()
    install_correlation_middleware(isolated)

    @isolated.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    local = TestClient(isolated)
    response = local.get("/ping", headers={CORRELATION_ID_HEADER: "iso-corr"})
    assert response.headers[CORRELATION_ID_HEADER] == "iso-corr"
