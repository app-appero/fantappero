"""Rilancio sync fixture per qualità dati (EP04-07)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.fixtures.models import Fixture
from sports_data.fixtures.sync import (
    FixtureDetailBatch,
    FixtureSyncResult,
    sync_fixtures,
)
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.provider.types import ProviderEnvelope
from sports_data.quality.models import SportsDataQualityIssue, SportsDataSyncRetry
from sports_data.quality.rules import validate_retry_target
from sports_data.quality.types import SyncRetryStatus

logger = get_logger(__name__)

QUALITY_RETRY_RUNS_TOTAL = "sports_data_quality_retry_runs_total"
QUALITY_RETRY_DURATION_SECONDS = "sports_data_quality_retry_duration_seconds"


class QualityRetryError(Exception):
    """Errore di dominio sul rilancio sync."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _counters_dict(result: FixtureSyncResult) -> dict[str, int]:
    c = result.counters
    return {
        "fixtures_created": c.fixtures_created,
        "fixtures_updated": c.fixtures_updated,
        "fixtures_unchanged": c.fixtures_unchanged,
        "events_created": c.events_created,
        "events_updated": c.events_updated,
        "events_corrected": c.events_corrected,
        "events_retracted": c.events_retracted,
        "lineups_created": c.lineups_created,
        "stats_created": c.stats_created,
        "stats_corrected": c.stats_corrected,
    }


def create_retry_audit(
    session: Session,
    *,
    fixture_provider_id: int,
    fixture_id: UUID | None = None,
    issue_id: UUID | None = None,
    requested_by_user_id: UUID | None = None,
    trigger: str = "operator_retry",
) -> SportsDataSyncRetry:
    validate_retry_target(fixture_provider_id=fixture_provider_id)
    now = datetime.now(UTC)
    row = SportsDataSyncRetry(
        issue_id=issue_id,
        fixture_id=fixture_id,
        fixture_provider_id=fixture_provider_id,
        requested_by_user_id=requested_by_user_id,
        trigger=trigger,
        status=SyncRetryStatus.QUEUED.value,
        started_at=now,
    )
    session.add(row)
    session.flush()
    return row


def sync_single_fixture_offline(
    session: Session,
    *,
    fixture_provider_id: int,
    fixtures_envelope: ProviderEnvelope | None = None,
    events_envelope: ProviderEnvelope | None = None,
    lineups_envelope: ProviderEnvelope | None = None,
    players_envelope: ProviderEnvelope | None = None,
    store_snapshots: bool = True,
) -> FixtureSyncResult:
    """Rilancio sync da envelope (test / corpus offline) senza modifiche opache."""
    validate_retry_target(fixture_provider_id=fixture_provider_id)
    fixtures_envelopes = [fixtures_envelope] if fixtures_envelope is not None else []
    detail_batches = [
        FixtureDetailBatch(
            fixture_provider_id=fixture_provider_id,
            events_envelope=events_envelope,
            lineups_envelope=lineups_envelope,
            players_envelope=players_envelope,
        ),
    ]
    return sync_fixtures(
        session,
        fixtures_envelopes=fixtures_envelopes,
        detail_batches=detail_batches,
        store_snapshots=store_snapshots,
    )


def sync_single_fixture_with_client(
    session: Session,
    client: ApiFootballClient,
    *,
    fixture_provider_id: int,
    store_snapshots: bool = True,
) -> FixtureSyncResult:
    """Rilancio sync trasparente: fetch provider per id fixture + dettagli."""
    validate_retry_target(fixture_provider_id=fixture_provider_id)
    fixtures_envelope = client.get("/fixtures", {"id": fixture_provider_id})
    events = client.get("/fixtures/events", {"fixture": fixture_provider_id})
    lineups = client.get("/fixtures/lineups", {"fixture": fixture_provider_id})
    players = client.get("/fixtures/players", {"fixture": fixture_provider_id})
    return sync_single_fixture_offline(
        session,
        fixture_provider_id=fixture_provider_id,
        fixtures_envelope=fixtures_envelope,
        events_envelope=events,
        lineups_envelope=lineups,
        players_envelope=players,
        store_snapshots=store_snapshots,
    )


def complete_retry(
    session: Session,
    retry: SportsDataSyncRetry,
    *,
    result: FixtureSyncResult | None = None,
    error: QualityRetryError | Exception | None = None,
) -> SportsDataSyncRetry:
    now = datetime.now(UTC)
    retry.finished_at = now
    if error is not None:
        retry.status = SyncRetryStatus.FAILED.value
        if isinstance(error, QualityRetryError):
            retry.error_code = error.code
            retry.error_message = error.message
        else:
            retry.error_code = "sync_failed"
            retry.error_message = type(error).__name__
        get_metrics().incr(
            QUALITY_RETRY_RUNS_TOTAL,
            labels={"provider": PROVIDER_NAME, "status": "failed"},
        )
        logger.warning(
            "sports_data_quality_retry_failed",
            extra={
                "provider": PROVIDER_NAME,
                "fixture_provider_id": retry.fixture_provider_id,
                "error_code": retry.error_code,
            },
        )
        return retry

    assert result is not None
    retry.status = SyncRetryStatus.OK.value
    retry.counters = _counters_dict(result)
    retry.error_code = None
    retry.error_message = None
    get_metrics().incr(
        QUALITY_RETRY_RUNS_TOTAL,
        labels={"provider": PROVIDER_NAME, "status": "ok"},
    )
    logger.info(
        "sports_data_quality_retry_ok",
        extra={
            "provider": PROVIDER_NAME,
            "fixture_provider_id": retry.fixture_provider_id,
            "events_corrected": retry.counters.get("events_corrected", 0),
            "events_retracted": retry.counters.get("events_retracted", 0),
        },
    )
    return retry


def run_retry(
    session: Session,
    retry_id: UUID,
    *,
    client: ApiFootballClient | None = None,
    offline_payloads: dict[str, ProviderEnvelope | None] | None = None,
) -> SportsDataSyncRetry:
    """Esegue un retry auditato (provider o payload offline)."""
    retry = session.get(SportsDataSyncRetry, retry_id)
    if retry is None:
        raise QualityRetryError("retry_not_found", "Rilancio sync non trovato")

    retry.status = SyncRetryStatus.RUNNING.value
    session.flush()
    metrics = get_metrics()
    labels = {"provider": PROVIDER_NAME}
    try:
        with Timer(metrics, QUALITY_RETRY_DURATION_SECONDS, labels=labels):
            if offline_payloads is not None:
                result = sync_single_fixture_offline(
                    session,
                    fixture_provider_id=retry.fixture_provider_id,
                    fixtures_envelope=offline_payloads.get("fixtures"),
                    events_envelope=offline_payloads.get("events"),
                    lineups_envelope=offline_payloads.get("lineups"),
                    players_envelope=offline_payloads.get("players"),
                )
            elif client is not None:
                result = sync_single_fixture_with_client(
                    session,
                    client,
                    fixture_provider_id=retry.fixture_provider_id,
                )
            else:
                raise QualityRetryError(
                    "provider_unavailable",
                    "Provider non configurato: impossibile rilanciare la sync",
                )
        complete_retry(session, retry, result=result)
    except QualityRetryError as exc:
        complete_retry(session, retry, error=exc)
    except Exception as exc:
        complete_retry(session, retry, error=exc)
        raise
    return retry


def resolve_issue_target(
    session: Session,
    issue_id: UUID,
) -> tuple[SportsDataQualityIssue, Fixture | None]:
    issue = session.get(SportsDataQualityIssue, issue_id)
    if issue is None:
        raise QualityRetryError("issue_not_found", "Issue di qualità non trovata")
    if issue.fixture_provider_id is None:
        raise QualityRetryError(
            "fixture_missing",
            "Issue senza fixture provider: impossibile rilanciare la sync",
        )
    fixture = None
    if issue.fixture_id is not None:
        fixture = session.get(Fixture, issue.fixture_id)
    if fixture is None:
        fixture = session.execute(
            select(Fixture).where(Fixture.provider_id == issue.fixture_provider_id),
        ).scalar_one_or_none()
    return issue, fixture
