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


def test_prometheus_snapshot_escapes_labels_and_exports_histogram_parts() -> None:
    metrics = get_metrics()
    labels = {"route:name": '/leagues/{id}\n"quoted"'}
    metrics.incr("requests-total", labels=labels, amount=2)
    metrics.observe("duration.seconds", 0.25, labels=labels)
    metrics.set_gauge("queue-depth", 3, labels={"queue": "celery"})

    rendered = metrics.render_prometheus()

    assert "# TYPE requests_total counter" in rendered
    assert 'requests_total{route_name="/leagues/{id}\\n\\"quoted\\""} 2.0' in rendered
    assert "duration_seconds_count" in rendered
    assert "duration_seconds_sum" in rendered
    assert "duration_seconds_max" in rendered
    assert 'queue_depth{queue="celery"} 3' in rendered


def test_prometheus_snapshot_declares_each_metric_family_once() -> None:
    metrics = get_metrics()
    metrics.incr("requests_total", labels={"status": "200"})
    metrics.incr("requests_total", labels={"status": "404"})
    metrics.observe("duration_seconds", 0.1, labels={"status": "200"})
    metrics.observe("duration_seconds", 0.2, labels={"status": "404"})

    rendered = metrics.render_prometheus()

    assert rendered.count("# TYPE requests_total counter") == 1
    assert rendered.count("# TYPE duration_seconds_count gauge") == 1
    assert rendered.count("# TYPE duration_seconds_sum gauge") == 1
    assert rendered.count("# TYPE duration_seconds_max gauge") == 1


def test_metrics_use_route_template_instead_of_dynamic_identifier() -> None:
    app = FastAPI()
    install_correlation_middleware(app)

    @app.get("/items/{item_id}")
    def item(item_id: str) -> dict[str, str]:
        return {"id": item_id}

    response = TestClient(app).get("/items/abc-123")
    assert response.status_code == 200
    assert (
        get_metrics().get_counter(
            HTTP_REQUESTS_TOTAL,
            labels={"method": "GET", "path": "/items/{item_id}", "status": "200"},
        )
        == 1.0
    )


def test_error_metrics_use_route_template_instead_of_dynamic_identifier() -> None:
    app = FastAPI()
    install_correlation_middleware(app)

    @app.get("/items/{item_id}")
    def broken_item(item_id: str) -> None:
        raise RuntimeError(item_id)

    response = TestClient(app, raise_server_exceptions=False).get("/items/abc-123")
    assert response.status_code == 500
    assert (
        get_metrics().get_counter(
            HTTP_REQUEST_ERRORS_TOTAL,
            labels={
                "method": "GET",
                "path": "/items/{item_id}",
                "error_type": "RuntimeError",
            },
        )
        == 1.0
    )


def test_unmatched_paths_share_one_bounded_metric_label() -> None:
    client = _app_with_routes()

    assert client.get("/missing/first-id").status_code == 404
    assert client.get("/missing/second-id").status_code == 404

    assert (
        get_metrics().get_counter(
            HTTP_REQUESTS_TOTAL,
            labels={"method": "GET", "path": "<unmatched>", "status": "404"},
        )
        == 2.0
    )
