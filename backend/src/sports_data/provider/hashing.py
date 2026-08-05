"""Canonical hashing helpers for provider snapshot idempotency."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Deterministic JSON bytes (sorted keys, compact, UTF-8)."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return text.encode("utf-8")


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def request_fingerprint(endpoint: str, params: Mapping[str, Any] | None = None) -> str:
    """Stable fingerprint for endpoint + query parameters (page excluded for logical identity).

    Page number is part of pagination I/O but snapshot identity for a full merged
    response uses params without ``page``. Single-page stores may include ``page``.
    """
    normalized = {str(k): str(v) for k, v in (params or {}).items() if v is not None}
    normalized.pop("page", None)
    material = {"endpoint": endpoint, "parameters": dict(sorted(normalized.items()))}
    return payload_sha256(material)
