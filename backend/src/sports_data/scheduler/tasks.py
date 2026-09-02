"""Celery beat tasks for sports pre/live/post/late polling (EP04-06)."""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from fantasy_turns.live_pipeline import process_live_fantasy_rounds
from sports_data.provider.client import build_client_from_settings
from sports_data.provider.errors import ProviderConfigError
from sports_data.scheduler.locks import RedisJobLock
from sports_data.scheduler.runner import PollCycleResult, run_poll_cycle
from sports_data.scheduler.windows import PollWindow


def _scheduler_enabled(settings: object) -> bool:
    return bool(getattr(settings, "sports_scheduler_enabled", False))


def _redis_url(settings: object) -> str:
    url = getattr(settings, "redis_url", None) or "redis://127.0.0.1:6379/0"
    return str(url)


def _run_window(window: PollWindow) -> dict[str, object]:
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    lock = RedisJobLock(_redis_url(settings))
    enabled = _scheduler_enabled(settings)
    try:
        if not enabled:
            with session_scope(factory) as session:
                result = run_poll_cycle(
                    session,
                    window,
                    lock=lock,
                    client=None,
                    enabled=False,
                    fetch_from_provider=False,
                )
            return _as_dict(result)

        try:
            client_cm = build_client_from_settings(settings)
        except ProviderConfigError:
            with session_scope(factory) as session:
                result = run_poll_cycle(
                    session,
                    window,
                    lock=lock,
                    client=None,
                    enabled=False,
                    fetch_from_provider=False,
                )
            return _as_dict(result)

        with client_cm as client:
            with session_scope(factory) as session:
                result = run_poll_cycle(
                    session,
                    window,
                    lock=lock,
                    client=client,
                    enabled=True,
                )
                pipeline = (
                    process_live_fantasy_rounds(session)
                    if window in {PollWindow.LIVE, PollWindow.POST_MATCH}
                    else None
                )
    finally:
        engine.dispose()
    payload = _as_dict(result)
    if pipeline is not None:
        payload["fantasy_pipeline"] = pipeline.as_dict()
    return payload


def _as_dict(result: PollCycleResult) -> dict[str, object]:
    return {
        "window": result.window.value,
        "status": result.status,
        "quota_mode": result.quota_mode.value,
        "fixtures_considered": result.fixtures_considered,
        "fixtures_polled": result.fixtures_polled,
        "provider_requests": result.provider_requests,
        "run_id": str(result.run_id) if result.run_id else None,
        "error_code": result.error_code,
    }


@celery_app.task(name="sports_data.poll_live_window")
def poll_live_window_task() -> dict[str, object]:
    return _run_window(PollWindow.LIVE)


@celery_app.task(name="sports_data.poll_pre_match_window")
def poll_pre_match_window_task() -> dict[str, object]:
    return _run_window(PollWindow.PRE_MATCH)


@celery_app.task(name="sports_data.poll_post_match_window")
def poll_post_match_window_task() -> dict[str, object]:
    return _run_window(PollWindow.POST_MATCH)


@celery_app.task(name="sports_data.poll_late_corrections_window")
def poll_late_corrections_window_task() -> dict[str, object]:
    return _run_window(PollWindow.LATE_CORRECTIONS)
