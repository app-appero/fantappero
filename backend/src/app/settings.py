"""Environment settings for local/container runtime (EP01-04).

Thin compatibility layer over typed ``config.settings`` schemas.
Runtime getters instantiate fresh settings so probes reflect the current env
(e.g. tests that monkeypatch variables after import).
"""

from __future__ import annotations

from config.settings.api import ApiSettings
from config.settings.worker import WorkerSettings


def database_url() -> str | None:
    return ApiSettings().database_url


def redis_url() -> str | None:
    return ApiSettings().redis_url


def celery_broker_url() -> str:
    return WorkerSettings().resolved_broker_url()


def celery_result_backend() -> str:
    return WorkerSettings().resolved_result_backend()
