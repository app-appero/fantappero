"""Idempotent persistence of provider envelopes into ``provider_snapshots``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.provider.hashing import payload_sha256, request_fingerprint
from sports_data.provider.models import ProviderSnapshot
from sports_data.provider.types import ProviderEnvelope

logger = get_logger(__name__)

PROVIDER_SNAPSHOTS_STORED_TOTAL = "provider_snapshots_stored_total"
PROVIDER_SNAPSHOTS_DEDUPED_TOTAL = "provider_snapshots_deduped_total"


def store_provider_snapshot(
    session: Session,
    envelope: ProviderEnvelope,
    *,
    provider: str = PROVIDER_NAME,
    fetched_at: datetime | None = None,
    request_params: dict[str, Any] | None = None,
) -> tuple[ProviderSnapshot, bool]:
    """Insert snapshot if new content; return ``(row, created)``.

    Idempotent for identical ``(provider, endpoint, fingerprint, payload_hash)``.
    """
    params = request_params if request_params is not None else dict(envelope.parameters)
    fingerprint = request_fingerprint(envelope.endpoint, params)
    body = envelope.raw or {
        "get": envelope.endpoint.lstrip("/"),
        "parameters": envelope.parameters,
        "errors": envelope.errors,
        "results": envelope.results,
        "paging": {
            "current": envelope.paging.current,
            "total": envelope.paging.total,
        },
        "response": envelope.response,
    }
    digest = payload_sha256(body)
    when = fetched_at or datetime.now(UTC)
    rate = envelope.rate_limit

    stmt = (
        insert(ProviderSnapshot)
        .values(
            provider=provider,
            endpoint=envelope.endpoint,
            request_fingerprint=fingerprint,
            payload_hash=digest,
            fetched_at=when,
            page_current=envelope.paging.current,
            page_total=envelope.paging.total,
            results_count=envelope.results,
            http_status=envelope.http_status,
            rate_limit_remaining=rate.remaining if rate else None,
            rate_limit_limit=rate.limit if rate else None,
            payload=body,
        )
        .on_conflict_do_nothing(
            constraint="uq_provider_snapshots_content",
        )
        .returning(ProviderSnapshot.id)
    )
    inserted_id: UUID | None = session.execute(stmt).scalar_one_or_none()
    metrics = get_metrics()
    labels = {"provider": provider, "endpoint": envelope.endpoint}

    if inserted_id is not None:
        session.flush()
        row = session.get(ProviderSnapshot, inserted_id)
        assert row is not None
        metrics.incr(PROVIDER_SNAPSHOTS_STORED_TOTAL, labels={**labels, "result": "created"})
        logger.info(
            "provider_snapshot_stored",
            extra={
                "provider": provider,
                "endpoint": envelope.endpoint,
                "payload_hash": digest,
                "results": envelope.results,
            },
        )
        return row, True

    existing = session.execute(
        select(ProviderSnapshot).where(
            ProviderSnapshot.provider == provider,
            ProviderSnapshot.endpoint == envelope.endpoint,
            ProviderSnapshot.request_fingerprint == fingerprint,
            ProviderSnapshot.payload_hash == digest,
        )
    ).scalar_one()
    metrics.incr(PROVIDER_SNAPSHOTS_DEDUPED_TOTAL, labels=labels)
    metrics.incr(PROVIDER_SNAPSHOTS_STORED_TOTAL, labels={**labels, "result": "deduped"})
    logger.info(
        "provider_snapshot_deduped",
        extra={
            "provider": provider,
            "endpoint": envelope.endpoint,
            "payload_hash": digest,
        },
    )
    return existing, False
