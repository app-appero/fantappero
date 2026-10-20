"""Pubblicazione eventi su Redis.

Mai bloccante: senza Redis il tempo reale resta spento e i client continuano
col polling di sempre.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any
from uuid import UUID

import redis
from sqlalchemy import event
from sqlalchemy.orm import Session

from config.settings.loader import get_api_settings
from observability.logging import get_logger

logger = get_logger(__name__)

_PENDING_KEY = "realtime_pending"


def user_channel(user_id: UUID | str) -> str:
    return f"rt:user:{user_id}"


def league_channel(league_id: UUID | str) -> str:
    return f"rt:league:{league_id}"


@lru_cache(maxsize=1)
def _client() -> redis.Redis | None:
    url = get_api_settings().redis_url
    if not url:
        return None
    return redis.Redis.from_url(url, socket_timeout=1.0, socket_connect_timeout=1.0)


def publish(channel: str, payload: dict[str, Any]) -> None:
    try:
        client = _client()
        if client is None:
            return
        client.publish(channel, json.dumps(payload, separators=(",", ":")))
    except Exception:
        logger.warning("realtime_publish_failed", exc_info=True)


def publish_after_commit(session: Session, channel: str, payload: dict[str, Any]) -> None:
    """Pubblica solo a transazione confermata: chi ricarica deve vedere il dato."""
    pending: list[tuple[str, dict[str, Any]]] | None = session.info.get(_PENDING_KEY)
    if pending is None:
        pending = session.info[_PENDING_KEY] = []
        queue = pending

        @event.listens_for(session, "after_commit")
        def _flush(_session: Session) -> None:
            items = list(queue)
            queue.clear()
            for item_channel, item_payload in items:
                publish(item_channel, item_payload)

        @event.listens_for(session, "after_rollback")
        def _drop(_session: Session) -> None:
            queue.clear()

    pending.append((channel, payload))
