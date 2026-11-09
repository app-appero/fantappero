"""One-time pickup code for the mobile Google login handoff (EP12-04 follow-up).

The web handoff page (``/accedi/google-app``) now exchanges the Google ID token for our own
session right there, in the browser, over HTTPS straight to this API — the Google token never
leaves the page. What crosses the ``fantappero://...`` deep link back to the app afterwards is
one random, single-use code with a short TTL, never a usable token.

Why this matters: ``fantappero://`` is a bare custom URL scheme with no Android App Link / iOS
Universal Link domain verification configured (``apps/mobile/app.json``), so another app
installed on the same phone could in principle register the same scheme and intercept the
return link before the real app sees it. Migrating to verified App Links/Universal Links is the
real fix and needs its own infra work (a verified HTTPS domain, signing, hosting
assetlinks.json / apple-app-site-association); until then, this at least keeps whatever crosses
that link cheap to steal and useless once stolen: it is our own code, not Google's token or our
session tokens, it is claimable exactly once, and it is dead within ``CODE_TTL_SECONDS``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from typing import Any

import redis

logger = logging.getLogger(__name__)

_KEY_PREFIX = "auth:mobile_handoff:"

#: Generous enough for the app to regain focus and call claim, short enough that an
#: intercepted link is worthless moments later even if the attacker reacts immediately.
CODE_TTL_SECONDS = 90


class MobileHandoffStore:
    """Redis-backed, single-use, short-lived code -> JSON payload mapping."""

    def __init__(self, redis_url: str) -> None:
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def put(self, payload: dict[str, Any]) -> str:
        """Store ``payload`` and return the one-time code that unlocks it."""
        code = secrets.token_urlsafe(32)
        key = _KEY_PREFIX + self._hash(code)
        # NX: never overwrite an existing key — token_urlsafe(32) collisions are not a
        # real-world concern, but this keeps the operation honestly atomic either way.
        self._client.set(key, json.dumps(payload), ex=CODE_TTL_SECONDS, nx=True)
        return code

    def claim(self, code: str) -> dict[str, Any] | None:
        """Return and delete the payload for ``code``; ``None`` if missing, expired, or
        already claimed. GETDEL makes the read-then-delete atomic: two near-simultaneous
        claims (the real app and whoever else got the link) can never both succeed."""
        key = _KEY_PREFIX + self._hash(code)
        raw = self._client.getdel(key)
        if raw is None:
            return None
        return json.loads(raw)

    @staticmethod
    def _hash(code: str) -> str:
        # Stored hashed, like the opaque refresh tokens elsewhere in this module (defense in
        # depth: a Redis dump or log of keys never hands out a usable code).
        return hashlib.sha256(code.encode("utf-8")).hexdigest()
