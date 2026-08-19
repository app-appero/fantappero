"""Servizio di dominio per il pannello qualità dati (EP04-07)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user import User
from config.settings.loader import get_api_settings
from sports_data.provider.client import build_client_from_settings
from sports_data.provider.errors import ProviderConfigError
from sports_data.quality.models import SportsDataQualityIssue, SportsDataSyncRetry
from sports_data.quality.retry import (
    QualityRetryError,
    create_retry_audit,
    resolve_issue_target,
    run_retry,
)
from sports_data.quality.scan import QualityScanResult, quality_summary, scan_quality
from sports_data.quality.schemas import (
    QualityIssueResponse,
    QualityScanResponse,
    QualitySummaryResponse,
    SyncRetryResponse,
)
from sports_data.quality.types import QualityIssueStatus


class SportsDataQualityService:
    """API di dominio: scan, elenco issue, rilancio sync auditato."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self) -> QualitySummaryResponse:
        data = quality_summary(self._session)
        return QualitySummaryResponse(
            open_total=data["open_total"],
            by_kind=data["by_kind"],
            by_severity=data["by_severity"],
            by_status=data["by_status"],
        )

    def list_issues(
        self,
        *,
        kind: str | None = None,
        status: str | None = QualityIssueStatus.OPEN.value,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QualityIssueResponse]:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        query = select(SportsDataQualityIssue).order_by(
            SportsDataQualityIssue.detected_at.desc(),
        )
        if kind:
            query = query.where(SportsDataQualityIssue.kind == kind)
        if status:
            query = query.where(SportsDataQualityIssue.status == status)
        rows = self._session.execute(query.offset(offset).limit(limit)).scalars().all()
        return [self._to_issue(row) for row in rows]

    def run_scan(self, *, fixture_id: UUID | None = None) -> QualityScanResponse:
        fixture_ids = [fixture_id] if fixture_id is not None else None
        result: QualityScanResult = scan_quality(self._session, fixture_ids=fixture_ids)
        self._session.flush()
        return QualityScanResponse(
            fixtures_scanned=result.counters.fixtures_scanned,
            findings=result.counters.findings,
            issues_created=result.counters.issues_created,
            issues_updated=result.counters.issues_updated,
            issues_resolved=result.counters.issues_resolved,
        )

    def request_retry_for_issue(
        self,
        *,
        issue_id: UUID,
        operator: User,
    ) -> SyncRetryResponse:
        issue, fixture = resolve_issue_target(self._session, issue_id)
        retry = create_retry_audit(
            self._session,
            fixture_provider_id=issue.fixture_provider_id or 0,
            fixture_id=fixture.id if fixture is not None else issue.fixture_id,
            issue_id=issue.id,
            requested_by_user_id=operator.id,
            trigger="operator_retry",
        )
        self._session.flush()
        return self._execute_retry(retry.id)

    def request_retry_for_fixture(
        self,
        *,
        fixture_provider_id: int,
        operator: User,
    ) -> SyncRetryResponse:
        from sports_data.fixtures.models import Fixture

        fixture = self._session.execute(
            select(Fixture).where(Fixture.provider_id == fixture_provider_id),
        ).scalar_one_or_none()
        retry = create_retry_audit(
            self._session,
            fixture_provider_id=fixture_provider_id,
            fixture_id=fixture.id if fixture is not None else None,
            requested_by_user_id=operator.id,
            trigger="operator_retry",
        )
        self._session.flush()
        return self._execute_retry(retry.id)

    def list_retries(self, *, limit: int = 50) -> list[SyncRetryResponse]:
        limit = max(1, min(limit, 200))
        rows = (
            self._session.execute(
                select(SportsDataSyncRetry)
                .order_by(SportsDataSyncRetry.started_at.desc())
                .limit(limit),
            )
            .scalars()
            .all()
        )
        return [self._to_retry(row) for row in rows]

    def get_retry(self, retry_id: UUID) -> SyncRetryResponse:
        row = self._session.get(SportsDataSyncRetry, retry_id)
        if row is None:
            raise QualityRetryError("retry_not_found", "Rilancio sync non trovato")
        return self._to_retry(row)

    def _execute_retry(self, retry_id: UUID) -> SyncRetryResponse:
        """Esegue sync in-process (auditata); il task Celery resta per job on-demand."""
        settings = get_api_settings()
        try:
            with build_client_from_settings(settings) as client:
                row = run_retry(self._session, retry_id, client=client)
        except ProviderConfigError as exc:
            from sports_data.quality.retry import complete_retry

            row = self._session.get(SportsDataSyncRetry, retry_id)
            if row is None:
                raise QualityRetryError("retry_not_found", "Rilancio sync non trovato") from exc
            complete_retry(
                self._session,
                row,
                error=QualityRetryError(
                    "provider_unavailable",
                    "Chiave provider assente: impossibile rilanciare la sync",
                ),
            )
        self._session.flush()
        return self._to_retry(row)

    @staticmethod
    def _to_issue(row: SportsDataQualityIssue) -> QualityIssueResponse:
        return QualityIssueResponse(
            id=str(row.id),
            fingerprint=row.fingerprint,
            kind=row.kind,
            code=row.code,
            severity=row.severity,
            status=row.status,
            title=row.title,
            message=row.message,
            fixture_id=str(row.fixture_id) if row.fixture_id else None,
            fixture_provider_id=row.fixture_provider_id,
            details=row.details or {},
            detected_at=row.detected_at,
            resolved_at=row.resolved_at,
            last_seen_at=row.last_seen_at,
        )

    @staticmethod
    def _to_retry(row: SportsDataSyncRetry) -> SyncRetryResponse:
        return SyncRetryResponse(
            id=str(row.id),
            issue_id=str(row.issue_id) if row.issue_id else None,
            fixture_id=str(row.fixture_id) if row.fixture_id else None,
            fixture_provider_id=row.fixture_provider_id,
            status=row.status,
            trigger=row.trigger,
            counters=row.counters or {},
            error_code=row.error_code,
            error_message=row.error_message,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
