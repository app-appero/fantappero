"""Celery tasks for sports data quality panel (EP04-07)."""

from __future__ import annotations

from uuid import UUID

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.provider.client import build_client_from_settings
from sports_data.provider.errors import ProviderConfigError
from sports_data.quality.models import SportsDataSyncRetry
from sports_data.quality.retry import QualityRetryError, complete_retry, run_retry
from sports_data.quality.scan import scan_quality


@celery_app.task(name="sports_data.scan_quality")
def scan_quality_task(fixture_id: str | None = None) -> dict[str, int]:
    """Scan qualità on-demand (tutte le fixture o una sola)."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            ids = [UUID(fixture_id)] if fixture_id else None
            result = scan_quality(session, fixture_ids=ids)
            return {
                "fixtures_scanned": result.counters.fixtures_scanned,
                "findings": result.counters.findings,
                "issues_created": result.counters.issues_created,
                "issues_updated": result.counters.issues_updated,
                "issues_resolved": result.counters.issues_resolved,
            }
    finally:
        engine.dispose()


@celery_app.task(name="sports_data.retry_fixture_sync")
def retry_fixture_sync_task(retry_id: str) -> dict[str, object]:
    """Esegue un rilancio sync auditato verso il provider."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            try:
                with build_client_from_settings(settings) as client:
                    row = run_retry(session, UUID(retry_id), client=client)
            except ProviderConfigError as exc:
                row = session.get(SportsDataSyncRetry, UUID(retry_id))
                if row is None:
                    raise QualityRetryError("retry_not_found", "Rilancio sync non trovato") from exc
                complete_retry(
                    session,
                    row,
                    error=QualityRetryError(
                        "provider_unavailable",
                        "Chiave provider assente: impossibile rilanciare la sync",
                    ),
                )
            return {
                "retry_id": retry_id,
                "status": row.status,
                "fixture_provider_id": row.fixture_provider_id,
                "counters": row.counters or {},
                "error_code": row.error_code,
            }
    finally:
        engine.dispose()
