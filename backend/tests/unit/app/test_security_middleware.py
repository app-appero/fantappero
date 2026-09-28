"""Unit tests for request-level hardening middleware (EP12-04, finding #21)."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.security_middleware import _MAX_BODY_BYTES, install_body_size_guard


async def _echo_body_length(request):
    body = await request.body()
    return PlainTextResponse(str(len(body)))


def _build_app() -> Starlette:
    app = Starlette(routes=[Route("/echo", _echo_body_length, methods=["POST"])])
    install_body_size_guard(app)
    return app


def test_request_within_limit_is_accepted() -> None:
    client = TestClient(_build_app())
    response = client.post("/echo", content=b"x" * 1024)
    assert response.status_code == 200
    assert response.text == "1024"


def test_declared_content_length_over_limit_is_rejected_before_parsing() -> None:
    client = TestClient(_build_app())
    oversized = _MAX_BODY_BYTES + 1
    response = client.post(
        "/echo",
        content=b"x" * oversized,
        headers={"Content-Length": str(oversized)},
    )
    assert response.status_code == 413


def test_streamed_body_over_limit_without_content_length_is_rejected() -> None:
    client = TestClient(_build_app())

    def oversized_stream():
        chunk = b"x" * 1024
        for _ in range(_MAX_BODY_BYTES // len(chunk) + 2):
            yield chunk

    response = client.post("/echo", content=oversized_stream())
    assert response.status_code == 413
