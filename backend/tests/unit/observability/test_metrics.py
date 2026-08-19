"""Metrics for successful requests, HTTP errors, and failed jobs."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from observability.celery_signals import _on_task_failure, _on_task_postrun, _on_task_prerun
from observability.context import clear_context
from observability.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUEST_ERRORS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    JOBS_FAILED_TOTAL,
    JOBS_TOTAL,
    get_metrics,
    reset_metrics,
)
from observability.middleware import install_correlation_middleware


def setup_function() -> None:
    clear_context()
    reset_metrics()


def _app_with_routes() -> TestClient:
    app = FastAPI()
    install_correlation_middleware(app)

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_metrics_on_successful_request() -> None:
    client = _app_with_routes()
    response = client.get("/ok")
    assert response.status_code == 200
    metrics = get_metrics()
    assert (
        metrics.get_counter(
            HTTP_REQUESTS_TOTAL,
            labels={"method": "GET", "path": "/ok", "status": "200"},
        )
        == 1.0
    )
    hist = metrics.get_histogram(
        HTTP_REQUEST_DURATION_SECONDS,
        labels={"method": "GET", "path": "/ok", "status": "200"},
    )
    assert hist["count"] == 1.0
    assert hist["sum_seconds"] >= 0.0


def test_metrics_on_request_error() -> None:
    client = _app_with_routes()
    response = client.get("/boom")
    assert response.status_code == 500
    metrics = get_metrics()
    assert (
        metrics.get_counter(
            HTTP_REQUEST_ERRORS_TOTAL,
            labels={"method": "GET", "path": "/boom", "error_type": "RuntimeError"},
        )
        >= 1.0
    )
    assert (
        metrics.get_counter(
            HTTP_REQUESTS_TOTAL,
            labels={"method": "GET", "path": "/boom", "status": "500"},
        )
        == 1.0
    )


def test_metrics_on_failed_job() -> None:
    class _Task:
        name = "app.worker.fail"

    task = _Task()
    _on_task_prerun(sender=task, task_id="fail-1", task=task)
    _on_task_failure(sender=task, task_id="fail-1", exception=RuntimeError("intentional"))
    _on_task_postrun(sender=task, task_id="fail-1", task=task, state="FAILURE")

    metrics = get_metrics()
    assert metrics.get_counter(JOBS_FAILED_TOTAL, labels={"task": "app.worker.fail"}) == 1.0
    assert (
        metrics.get_counter(
            JOBS_TOTAL,
            labels={"task": "app.worker.fail", "state": "FAILURE"},
        )
        == 1.0
    )
