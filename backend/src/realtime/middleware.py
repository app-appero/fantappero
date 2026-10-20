"""Dopo ogni modifica riuscita al mercato di una lega, avvisa i membri (EP09-07).

Un unico punto invece di un hook per endpoint: scambi, buste, rilanci e
aggiudicazioni passano tutti da ``/leagues/{id}/mercato/...``. L'evento porta
solo tipo e id: il client ricarica i dati con le sue chiamate (e i suoi permessi).
"""

from __future__ import annotations

import asyncio
import re

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from realtime.publisher import league_channel, publish

_MARKET_PATH = re.compile(r"^/leagues/([0-9a-fA-F-]{36})/mercato/([^?]*)")
_SESSION = re.compile(r"asta-live/sessioni/([0-9a-fA-F-]{36})")
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def market_event(path: str) -> tuple[str, dict[str, str]] | None:
    match = _MARKET_PATH.match(path)
    if match is None:
        return None
    league_id, rest = match.group(1), match.group(2)
    if rest.startswith("scambi"):
        kind = "trades"
    elif rest.startswith("asta-live"):
        kind = "auction_live"
    else:
        kind = "market"
    payload = {"type": "market.updated", "kind": kind, "leagueId": league_id}
    session = _SESSION.search(rest)
    if session:
        payload["sessionId"] = session.group(1)
    return league_channel(league_id), payload


class RealtimeMarketMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _MUTATING:
            await self.app(scope, receive, send)
            return
        status = 500

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        await self.app(scope, receive, capture)
        if status < 300:
            found = market_event(scope["path"])
            if found is not None:
                await asyncio.to_thread(publish, *found)
