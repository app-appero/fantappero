"""FastAPI entrypoint with health probes and observability baseline (EP01-05)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.deps_health import aggregate_health
from auth.exceptions import AuthError
from auth.profile_router import router as profile_router
from auth.router import router as auth_router
from authorization.exceptions import AuthorizationError
from config.settings.loader import get_api_settings, validate_api_settings
from leagues.router import router as leagues_router
from observability.error_tracking import configure_error_tracking
from observability.health import as_readiness, liveness
from observability.logging import configure_logging
from observability.middleware import install_correlation_middleware
from sports_data.quality.retry import QualityRetryError
from sports_data.quality.router import quality_error_handler
from sports_data.quality.router import router as quality_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = validate_api_settings()
    configure_logging(settings.log_level)
    configure_error_tracking(
        enabled=settings.error_tracking_enabled,
        dsn=settings.error_tracking_dsn,
    )
    avatar_dir = Path(settings.avatar_storage_path)
    avatar_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="FantApperò API",
    version="0.0.0",
    description="Scaffold health surface — local stack wires Postgres/Redis (EP01-02).",
    lifespan=lifespan,
)
install_correlation_middleware(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(leagues_router)
app.include_router(quality_router)
app.add_exception_handler(QualityRetryError, quality_error_handler)

_avatar_settings = get_api_settings()
_avatar_mount = Path(_avatar_settings.avatar_storage_path)
_avatar_mount.mkdir(parents=True, exist_ok=True)
app.mount("/media/avatars", StaticFiles(directory=str(_avatar_mount)), name="avatars")


@app.exception_handler(AuthError)
def auth_error_handler(_request: object, exc: AuthError) -> JSONResponse:
    status_code = 400
    if exc.code == "invalid_credentials":
        status_code = 401
    elif exc.code == "email_not_verified":
        status_code = 403
    elif exc.code == "rate_limit_exceeded":
        status_code = 429
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )


@app.exception_handler(AuthorizationError)
def authorization_error_handler(_request: object, exc: AuthorizationError) -> JSONResponse:
    status_code = 403
    if exc.code == "league_not_found":
        status_code = 404
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )


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
