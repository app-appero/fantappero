"""Revocation marker for impersonation access tokens (EP12-04 follow-up, finding #2).

An impersonation token is a normal JWT access token under the hood — stateless, so by
itself it cannot be killed before it expires. This store adds a side-channel "is this
jti still active" check in Redis: :meth:`start` records the token's jti with the same
TTL as the token itself, :meth:`is_active` is consulted on every authenticated request
carrying an ``imp`` claim, and :meth:`revoke_all_for_user` lets an operator cut off every
impersonation currently running against one account without having to know which jti.
"""

from __future__ import annotations

import logging
from uuid import UUID

import redis

logger = logging.getLogger(__name__)

_MARKER_PREFIX = "auth:impersonation:jti:"
_BY_USER_PREFIX = "auth:impersonation:by_user:"


class ImpersonationStore:
    def __init__(self, redis_url: str) -> None:
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def start(self, *, jti: str, target_user_id: UUID, ttl_seconds: int) -> None:
        marker_key = _MARKER_PREFIX + jti
        by_user_key = _BY_USER_PREFIX + str(target_user_id)
        try:
            pipe = self._client.pipeline()
            pipe.set(marker_key, str(target_user_id), ex=ttl_seconds)
            pipe.sadd(by_user_key, jti)
            pipe.expire(by_user_key, ttl_seconds)
            pipe.execute()
        except redis.RedisError:
            logger.warning("impersonation_store_unavailable", extra={"action": "start"})

    def is_active(self, jti: str) -> bool:
        try:
            return bool(self._client.exists(_MARKER_PREFIX + jti))
        except redis.RedisError:
            # Degrade open, like the rate limiter elsewhere: a Redis outage must not
            # lock every impersonated support session out, only skip the extra check.
            logger.warning("impersonation_store_unavailable", extra={"action": "is_active"})
            return True

    def revoke_all_for_user(self, target_user_id: UUID) -> int:
        by_user_key = _BY_USER_PREFIX + str(target_user_id)
        try:
            jtis = self._client.smembers(by_user_key)
            if not jtis:
                return 0
            marker_keys = [_MARKER_PREFIX + jti for jti in jtis]
            pipe = self._client.pipeline()
            pipe.delete(*marker_keys)
            pipe.delete(by_user_key)
            pipe.execute()
            return len(jtis)
        except redis.RedisError:
            logger.warning("impersonation_store_unavailable", extra={"action": "revoke_all"})
            return 0
