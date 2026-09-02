"""Request-level hardening that isn't tied to a specific domain (EP12-04).

Kept separate from ``observability/middleware.py`` (correlation IDs/metrics)
because this one exists purely to close a known upstream vulnerability, not
to add cross-cutting observability.
"""

from __future__ import annotations

from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

# Starlette <1.1.0 (all versions accepted by our pinned fastapi==0.116.1,
# which requires starlette<0.48.0) parses the `Range` request header with an
# O(n^2) regex + merge loop in `FileResponse._parse_range_header()` — see
# PYSEC-2026-1942 / GHSA (CPU exhaustion via a single crafted request). We
# serve real files via `StaticFiles` at /media/avatars
# (backend/src/app/main.py), so this is reachable and unauthenticated.
#
# Bumping fastapi to pull in a patched starlette needs a full regression pass
# (out of scope for a low-risk fix, see
# docs/operations/beta_readiness/ep12-04_security_review.md). Instead: reject
# any request with an implausibly long `Range` header *before* it reaches
# StaticFiles/FileResponse, which are the only vulnerable code paths in this
# app. The PoC needs a header value of several thousand characters to cause
# measurable CPU cost (0.05s at ~5,000 chars, 3.2s at ~40,000 chars); no
# legitimate client (browser image/video partial-content request) ever sends
# anything close to this — a single-range request is a few dozen characters,
# a handful of ranges comma-separated stays well under 200.
_MAX_RANGE_HEADER_LENGTH = 512


class RangeHeaderGuardMiddleware:
    """Reject requests with an oversized `Range` header (starlette DoS mitigation)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers") or []:
            if name == b"range" and len(value) > _MAX_RANGE_HEADER_LENGTH:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                    },
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"Range header too long.",
                    },
                )
                return

        await self.app(scope, receive, send)


def install_range_header_guard(app: Any) -> None:
    """Register the Range-header length guard on a FastAPI/Starlette app."""
    app.add_middleware(RangeHeaderGuardMiddleware)
