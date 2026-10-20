"""Canale SSE ``GET /realtime/stream`` (EP09-07).

Un solo flusso per client: eventi dell'utente (notifiche) più quelli delle
leghe richieste di cui è membro. Autenticazione Bearer come il resto dell'API.
I dipendenti ``yield`` di FastAPI 0.116 chiudono la sessione DB prima di
iniziare lo streaming: non restano connessioni DB aperte per ore. Se si passa
a FastAPI >= 0.118 va riverificato.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from auth.dependencies import _get_session_factory
from auth.models.user import User
from authorization.dependencies import require_permissions
from config.settings.loader import get_api_settings
from database.enums import Permission
from leagues.models.league_membership import LeagueMembership
from realtime.publisher import league_channel, user_channel

router = APIRouter(prefix="/realtime", tags=["realtime"])

HEARTBEAT_SECONDS = 15
# Il token d'accesso scade: a intervalli chiudiamo e il client si riconnette col nuovo.
MAX_STREAM_SECONDS = 600


def _member_leagues(user_id: UUID, league_ids: list[UUID]) -> list[UUID]:
    if not league_ids:
        return []
    with _get_session_factory()() as session:
        rows = session.scalars(
            select(LeagueMembership.league_id).where(
                LeagueMembership.user_id == user_id,
                LeagueMembership.league_id.in_(league_ids),
            )
        ).all()
    return list(rows)


async def _events(request: Request, redis_url: str, channels: list[str]) -> AsyncIterator[str]:
    client = aioredis.from_url(redis_url)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(*channels)
        yield "retry: 3000\n: connected\n\n"
        started = time.monotonic()
        while time.monotonic() - started < MAX_STREAM_SECONDS:
            if await request.is_disconnected():
                return
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=HEARTBEAT_SECONDS
            )
            if message is None:
                yield ": ping\n\n"
                continue
            data = message["data"]
            data = data.decode() if isinstance(data, bytes) else str(data)
            yield f"data: {data}\n\n"
    finally:
        await pubsub.aclose()
        await client.aclose()


@router.get("/stream", response_model=None)
async def stream(
    request: Request,
    league_ids: str = Query(default="", alias="leagueIds"),
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
) -> StreamingResponse | JSONResponse:
    redis_url = get_api_settings().redis_url
    if not redis_url:
        return JSONResponse(
            status_code=503,
            content={"message": "Tempo reale non disponibile.", "code": "realtime_unavailable"},
        )
    requested: list[UUID] = []
    for raw in league_ids.split(","):
        try:
            requested.append(UUID(raw.strip()))
        except ValueError:
            continue
    allowed = await run_in_threadpool(_member_leagues, current_user.id, requested[:20])
    channels = [user_channel(current_user.id), *(league_channel(lid) for lid in allowed)]
    return StreamingResponse(
        _events(request, redis_url, channels),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
