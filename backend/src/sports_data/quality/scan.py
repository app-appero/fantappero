"""Scan qualità dati: costruzione snapshot e persistenza idempotente (EP04-07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    PlayerMatchStat,
)
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.quality.models import SportsDataQualityIssue
from sports_data.quality.rules import FixtureQualitySnapshot, QualityFinding, detect_all
from sports_data.quality.types import QualityIssueStatus

logger = get_logger(__name__)

QUALITY_SCAN_RUNS_TOTAL = "sports_data_quality_scan_runs_total"
QUALITY_SCAN_ISSUES_TOTAL = "sports_data_quality_scan_issues_total"
QUALITY_SCAN_DURATION_SECONDS = "sports_data_quality_scan_duration_seconds"
QUALITY_OPEN_ISSUES = "sports_data_quality_open_issues"

CONFLICT_EVENT_STATUSES = frozenset({"anomaly", "provisional", "insufficient"})


@dataclass
class QualityScanCounters:
    fixtures_scanned: int = 0
    findings: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    issues_resolved: int = 0


@dataclass
class QualityScanResult:
    counters: QualityScanCounters = field(default_factory=QualityScanCounters)
    findings: list[QualityFinding] = field(default_factory=list)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def build_fixture_snapshot(session: Session, fixture: Fixture) -> FixtureQualitySnapshot:
    """Carica conteggi e segnali di conflitto/correzione per una fixture."""
    active_events = session.execute(
        select(func.count())
        .select_from(MatchEvent)
        .where(MatchEvent.fixture_id == fixture.id, MatchEvent.is_active.is_(True)),
    ).scalar_one()
    lineup_count = session.execute(
        select(func.count())
        .select_from(OfficialLineup)
        .where(OfficialLineup.fixture_id == fixture.id),
    ).scalar_one()
    stats_count = session.execute(
        select(func.count())
        .select_from(PlayerMatchStat)
        .where(PlayerMatchStat.fixture_id == fixture.id),
    ).scalar_one()

    conflict_rows = session.execute(
        select(MatchEvent)
        .where(
            MatchEvent.fixture_id == fixture.id,
            MatchEvent.is_active.is_(True),
        ),
    ).scalars()
    conflict_events: list[tuple[str, tuple[str, ...], str]] = []
    for row in conflict_rows:
        codes = tuple(str(c) for c in (row.anomaly_codes or []))
        status = (row.status or "").strip().lower()
        if codes or status in CONFLICT_EVENT_STATUSES:
            conflict_events.append((row.provider_event_key, codes, status))

    retracted_rows = session.execute(
        select(MatchEvent).where(
            MatchEvent.fixture_id == fixture.id,
            MatchEvent.is_active.is_(False),
        ),
    ).scalars()
    retracted_events = tuple(
        (row.provider_event_key, _as_utc(row.retracted_at)) for row in retracted_rows
    )

    return FixtureQualitySnapshot(
        fixture_id=fixture.id,
        fixture_provider_id=fixture.provider_id,
        status_short=fixture.status_short,
        kickoff_at=_as_utc(fixture.kickoff_at),
        active_event_count=int(active_events),
        lineup_count=int(lineup_count),
        stats_count=int(stats_count),
        conflict_events=tuple(conflict_events),
        retracted_events=retracted_events,
    )


def _upsert_finding(
    session: Session,
    finding: QualityFinding,
    *,
    now: datetime,
    counters: QualityScanCounters,
) -> SportsDataQualityIssue:
    row = session.execute(
        select(SportsDataQualityIssue).where(
            SportsDataQualityIssue.fingerprint == finding.fingerprint,
        ),
    ).scalar_one_or_none()
    if row is None:
        row = SportsDataQualityIssue(
            fingerprint=finding.fingerprint,
            kind=finding.kind.value,
            code=finding.code.value,
            severity=finding.severity.value,
            status=QualityIssueStatus.OPEN.value,
            title=finding.title,
            message=finding.message,
            fixture_id=finding.fixture_id,
            fixture_provider_id=finding.fixture_provider_id,
            details=finding.details,
            detected_at=now,
            last_seen_at=now,
        )
        session.add(row)
        counters.issues_created += 1
        get_metrics().incr(
            QUALITY_SCAN_ISSUES_TOTAL,
            labels={"provider": PROVIDER_NAME, "result": "created", "kind": finding.kind.value},
        )
        return row

    changed = (
        row.status != QualityIssueStatus.OPEN.value
        or row.title != finding.title
        or row.message != finding.message
        or row.details != finding.details
        or row.severity != finding.severity.value
    )
    row.kind = finding.kind.value
    row.code = finding.code.value
    row.severity = finding.severity.value
    row.title = finding.title
    row.message = finding.message
    row.fixture_id = finding.fixture_id
    row.fixture_provider_id = finding.fixture_provider_id
    row.details = finding.details
    row.last_seen_at = now
    if row.status != QualityIssueStatus.OPEN.value:
        row.status = QualityIssueStatus.OPEN.value
        row.resolved_at = None
        row.detected_at = now
    if changed:
        counters.issues_updated += 1
        get_metrics().incr(
            QUALITY_SCAN_ISSUES_TOTAL,
            labels={"provider": PROVIDER_NAME, "result": "updated", "kind": finding.kind.value},
        )
    else:
        get_metrics().incr(
            QUALITY_SCAN_ISSUES_TOTAL,
            labels={"provider": PROVIDER_NAME, "result": "unchanged", "kind": finding.kind.value},
        )
    return row


def scan_quality(
    session: Session,
    *,
    fixture_ids: list[UUID] | None = None,
    now: datetime | None = None,
) -> QualityScanResult:
    """Scansiona le fixture e aggiorna le issue in modo idempotente."""
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)

    metrics = get_metrics()
    labels = {"provider": PROVIDER_NAME}
    counters = QualityScanCounters()
    result = QualityScanResult(counters=counters)

    try:
        with Timer(metrics, QUALITY_SCAN_DURATION_SECONDS, labels=labels):
            query = select(Fixture)
            if fixture_ids is not None:
                if not fixture_ids:
                    metrics.incr(QUALITY_SCAN_RUNS_TOTAL, labels={**labels, "status": "ok"})
                    return result
                query = query.where(Fixture.id.in_(fixture_ids))
            fixtures = session.execute(query).scalars().all()

            seen_fingerprints: set[str] = set()
            for fixture in fixtures:
                counters.fixtures_scanned += 1
                snapshot = build_fixture_snapshot(session, fixture)
                findings = detect_all(snapshot, now=clock)
                for finding in findings:
                    seen_fingerprints.add(finding.fingerprint)
                    result.findings.append(finding)
                    counters.findings += 1
                    _upsert_finding(session, finding, now=clock, counters=counters)

            # Risolvi issue aperte non più rilevate (scope scan).
            open_q = select(SportsDataQualityIssue).where(
                SportsDataQualityIssue.status == QualityIssueStatus.OPEN.value,
            )
            if fixture_ids is not None:
                open_q = open_q.where(SportsDataQualityIssue.fixture_id.in_(fixture_ids))
            for open_issue in session.execute(open_q).scalars():
                if open_issue.fingerprint in seen_fingerprints:
                    continue
                if open_issue.status == QualityIssueStatus.DISMISSED.value:
                    continue
                open_issue.status = QualityIssueStatus.RESOLVED.value
                open_issue.resolved_at = clock
                counters.issues_resolved += 1
                get_metrics().incr(
                    QUALITY_SCAN_ISSUES_TOTAL,
                    labels={
                        "provider": PROVIDER_NAME,
                        "result": "resolved",
                        "kind": open_issue.kind,
                    },
                )

            open_count = session.execute(
                select(func.count())
                .select_from(SportsDataQualityIssue)
                .where(SportsDataQualityIssue.status == QualityIssueStatus.OPEN.value),
            ).scalar_one()
            metrics.set_gauge(QUALITY_OPEN_ISSUES, float(open_count), labels=labels)

        metrics.incr(QUALITY_SCAN_RUNS_TOTAL, labels={**labels, "status": "ok"})
        logger.info(
            "sports_data_quality_scan_ok",
            extra={
                "provider": PROVIDER_NAME,
                "fixtures_scanned": counters.fixtures_scanned,
                "findings": counters.findings,
                "issues_created": counters.issues_created,
                "issues_resolved": counters.issues_resolved,
            },
        )
    except Exception:
        metrics.incr(QUALITY_SCAN_RUNS_TOTAL, labels={**labels, "status": "error"})
        logger.exception("sports_data_quality_scan_failed", extra={"provider": PROVIDER_NAME})
        raise
    return result


def quality_summary(session: Session) -> dict[str, Any]:
    """Aggregati per il pannello operatore."""
    rows = session.execute(
        select(
            SportsDataQualityIssue.kind,
            SportsDataQualityIssue.severity,
            SportsDataQualityIssue.status,
            func.count(),
        ).group_by(
            SportsDataQualityIssue.kind,
            SportsDataQualityIssue.severity,
            SportsDataQualityIssue.status,
        ),
    ).all()
    by_kind: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    open_total = 0
    for kind, severity, status, count in rows:
        by_kind[kind] = by_kind.get(kind, 0) + int(count)
        by_severity[severity] = by_severity.get(severity, 0) + int(count)
        by_status[status] = by_status.get(status, 0) + int(count)
        if status == QualityIssueStatus.OPEN.value:
            open_total += int(count)
    return {
        "open_total": open_total,
        "by_kind": by_kind,
        "by_severity": by_severity,
        "by_status": by_status,
    }
