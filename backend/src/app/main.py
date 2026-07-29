"""FastAPI entrypoint with health probes, auth, and observability (EP01-05, EP02-01)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.cors import install_cors_middleware
from app.deps_auth import auth_error_to_http
from app.deps_health import aggregate_health
from app.routers import auth, leagues, users
from auth.errors import AuthError
from config.settings.api import ApiSettings
from config.settings.loader import validate_api_settings
from observability.error_tracking import configure_error_tracking
from observability.health import as_readiness, liveness
from observability.logging import configure_logging
from observability.middleware import install_correlation_middleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = validate_api_settings()
    configure_logging(settings.log_level)
    configure_error_tracking(
        enabled=settings.error_tracking_enabled,
        dsn=settings.error_tracking_dsn,
    )
    yield


app = FastAPI(
    title="FantApperò API",
    version="0.0.0",
    description=(
        "Health probes, auth, profiles, leagues, authorization, "
        "and privacy (EP01-02, EP02-01–04, EP03-01)."
    ),
    lifespan=lifespan,
)
install_cors_middleware(app, ApiSettings())
install_correlation_middleware(app)


@app.exception_handler(AuthError)
async def auth_error_handler(_request: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=auth_error_to_http(exc))


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(leagues.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "fantappero-api", "status": "ok"}


@app.get("/live")
def live() -> JSONResponse:
    """Liveness: process is running (no dependency checks)."""
    status_code, body = liveness()
    return JSONResponse(status_code=status_code, content=body)


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: configured dependencies must respond."""
    status_code, body = as_readiness(*aggregate_health())
    return JSONResponse(status_code=status_code, content=body)


@app.get("/health")
def health() -> JSONResponse:
    """
    Readiness alias kept for Compose healthchecks (EP01-02).

    Prefer ``/live`` vs ``/ready`` for new integrations.
    """
    status_code, body = as_readiness(*aggregate_health())
    return JSONResponse(status_code=status_code, content=body)
