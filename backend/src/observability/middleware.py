"""ASGI middleware: correlation IDs, request logs, and HTTP metrics."""

from __future__ import annotations

import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from observability.constants import CORRELATION_ID_HEADER, REQUEST_ID_HEADER
from observability.context import clear_context, set_correlation_id, set_request_id
from observability.error_tracking import get_error_tracker
from observability.logging import get_logger
from observability.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUEST_ERRORS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    get_metrics,
)
from observability.propagation import extract_inbound_correlation, extract_inbound_request_id

logger = get_logger(__name__)


def _headers_to_dict(raw: list[tuple[bytes, bytes]]) -> dict[str, str]:
    return {k.decode("latin-1"): v.decode("latin-1") for k, v in raw}


def _metric_path(scope: Scope) -> str:
    """Use a bounded route label, including for arbitrary unmatched paths."""
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    return str(route_path) if route_path else "<unmatched>"


class CorrelationMiddleware:
    """Propagate correlation/request IDs and record per-request metrics."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers_to_dict(list(scope.get("headers") or []))
        correlation_id = extract_inbound_correlation(headers)
        request_id = extract_inbound_request_id(headers, fallback=correlation_id)
        set_correlation_id(correlation_id)
        set_request_id(request_id)

        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        start = time.perf_counter()
        status_code = 500
        raised: BaseException | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
                raw_headers = list(message.get("headers") or [])
                corr_bytes = correlation_id.encode("latin-1")
                req_bytes = request_id.encode("latin-1")
                raw_headers.append((CORRELATION_ID_HEADER.lower().encode("latin-1"), corr_bytes))
                raw_headers.append((REQUEST_ID_HEADER.lower().encode("latin-1"), req_bytes))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            raised = exc
            metrics = get_metrics()
            metric_path = _metric_path(scope)
            metrics.incr(
                HTTP_REQUEST_ERRORS_TOTAL,
                labels={
                    "method": method,
                    "path": metric_path,
                    "error_type": type(exc).__name__,
                },
            )
            get_error_tracker().capture_exception(
                exc,
                context={"method": method, "path": path},
            )
            logger.error(
                "request_failed",
                extra={"method": method, "path": path, "error_type": type(exc).__name__},
                exc_info=exc,
            )
            raise
        finally:
            elapsed = time.perf_counter() - start
            metrics = get_metrics()
            metric_path = _metric_path(scope)
            labels = {
                "method": method,
                "path": metric_path,
                "status": str(status_code),
            }
            metrics.incr(HTTP_REQUESTS_TOTAL, labels=labels)
            metrics.observe(HTTP_REQUEST_DURATION_SECONDS, elapsed, labels=labels)
            if status_code >= 500 and raised is None:
                metrics.incr(
                    HTTP_REQUEST_ERRORS_TOTAL,
                    labels={
                        "method": method,
                        "path": metric_path,
                        "error_type": "http_5xx",
                    },
                )
            logger.info(
                "request_completed",
                extra={
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "duration_ms": round(elapsed * 1000, 3),
                },
            )
            clear_context()


def install_correlation_middleware(app: Any) -> None:
    """Register middleware on a FastAPI/Starlette app (outermost)."""
    app.add_middleware(CorrelationMiddleware)
