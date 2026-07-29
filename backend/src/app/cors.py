"""CORS configuration for browser clients (EP02-01)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings.api import ApiSettings


def install_cors_middleware(app: FastAPI, settings: ApiSettings | None = None) -> None:
    """Allow local web/Expo dev origins to call the API from the browser."""

    resolved = settings or ApiSettings()
    origins = resolved.cors_origin_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
