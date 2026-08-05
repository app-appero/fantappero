"""Regole pure di rilevamento qualità dati (EP04-07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sports_data.quality.types import (
    FINISHED_STATUSES,
    ISSUE_MESSAGES_IT,
    ISSUE_TITLES_IT,
    PRE_STATUSES,
    QualityIssueCode,
    QualityIssueKind,
    QualitySeverity,
)


@dataclass(frozen=True)
class FixtureQualitySnapshot:
    """Vista minimale di una fixture per le regole (senza ORM)."""

    fixture_id: UUID
    fixture_provider_id: int
    status_short: str
    kickoff_at: datetime | None
    active_event_count: int = 0
    lineup_count: int = 0
    stats_count: int = 0
    conflict_events: tuple[tuple[str, tuple[str, ...], str], ...] = ()
    # (provider_event_key, anomaly_codes, status)
    retracted_events: tuple[tuple[str, datetime | None], ...] = ()
    # (provider_event_key, retracted_at)


@dataclass(frozen=True)
class QualityFinding:
    """Esito deterministico di una regola su una fixture."""

    kind: QualityIssueKind
    code: QualityIssueCode
    severity: QualitySeverity
    fixture_id: UUID
    fixture_provider_id: int
    fingerprint: str
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def build_fingerprint(
    *,
    code: QualityIssueCode,
    fixture_provider_id: int,
    entity_ref: str = "fixture",
) -> str:
    """Chiave idempotente per issue aperte (stabile tra scan ripetute)."""
    return f"{code.value}:{fixture_provider_id}:{entity_ref}"


def _finding(
    *,
    kind: QualityIssueKind,
    code: QualityIssueCode,
    severity: QualitySeverity,
    snapshot: FixtureQualitySnapshot,
    entity_ref: str = "fixture",
    details: dict[str, Any] | None = None,
) -> QualityFinding:
    return QualityFinding(
        kind=kind,
        code=code,
        severity=severity,
        fixture_id=snapshot.fixture_id,
        fixture_provider_id=snapshot.fixture_provider_id,
        fingerprint=build_fingerprint(
            code=code,
            fixture_provider_id=snapshot.fixture_provider_id,
            entity_ref=entity_ref,
        ),
        title=ISSUE_TITLES_IT[code],
        message=ISSUE_MESSAGES_IT[code],
        details=details or {},
    )


def detect_missing(snapshot: FixtureQualitySnapshot) -> list[QualityFinding]:
    status = (snapshot.status_short or "").strip().upper()
    if status not in FINISHED_STATUSES:
        return []
    findings: list[QualityFinding] = []
    if snapshot.active_event_count == 0:
        findings.append(
            _finding(
                kind=QualityIssueKind.MISSING,
                code=QualityIssueCode.MISSING_EVENTS,
                severity=QualitySeverity.BLOCKING,
                snapshot=snapshot,
            )
        )
    if snapshot.lineup_count == 0:
        findings.append(
            _finding(
                kind=QualityIssueKind.MISSING,
                code=QualityIssueCode.MISSING_LINEUPS,
                severity=QualitySeverity.WARNING,
                snapshot=snapshot,
            )
        )
    if snapshot.stats_count == 0:
        findings.append(
            _finding(
                kind=QualityIssueKind.MISSING,
                code=QualityIssueCode.MISSING_STATS,
                severity=QualitySeverity.BLOCKING,
                snapshot=snapshot,
            )
        )
    return findings


def detect_delays(
    snapshot: FixtureQualitySnapshot,
    *,
    now: datetime | None = None,
) -> list[QualityFinding]:
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    status = (snapshot.status_short or "").strip().upper()
    findings: list[QualityFinding] = []

    if status == "PST":
        findings.append(
            _finding(
                kind=QualityIssueKind.DELAY,
                code=QualityIssueCode.POSTPONED,
                severity=QualitySeverity.WARNING,
                snapshot=snapshot,
                details={"status_short": status},
            )
        )

    if status in PRE_STATUSES and snapshot.kickoff_at is not None:
        kickoff = snapshot.kickoff_at
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=UTC)
        if kickoff < clock:
            findings.append(
                _finding(
                    kind=QualityIssueKind.DELAY,
                    code=QualityIssueCode.KICKOFF_OVERDUE,
                    severity=QualitySeverity.WARNING,
                    snapshot=snapshot,
                    details={
                        "status_short": status,
                        "kickoff_at": kickoff.isoformat(),
                    },
                )
            )
    return findings


def detect_conflicts(snapshot: FixtureQualitySnapshot) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for event_key, anomaly_codes, event_status in snapshot.conflict_events:
        findings.append(
            _finding(
                kind=QualityIssueKind.CONFLICT,
                code=QualityIssueCode.EVENT_CONFLICT,
                severity=QualitySeverity.BLOCKING,
                snapshot=snapshot,
                entity_ref=event_key,
                details={
                    "provider_event_key": event_key,
                    "anomaly_codes": list(anomaly_codes),
                    "event_status": event_status,
                },
            )
        )
    return findings


def detect_corrections(snapshot: FixtureQualitySnapshot) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for event_key, retracted_at in snapshot.retracted_events:
        details: dict[str, Any] = {"provider_event_key": event_key}
        if retracted_at is not None:
            details["retracted_at"] = retracted_at.isoformat()
        findings.append(
            _finding(
                kind=QualityIssueKind.CORRECTION,
                code=QualityIssueCode.EVENT_RETRACTED,
                severity=QualitySeverity.INFO,
                snapshot=snapshot,
                entity_ref=event_key,
                details=details,
            )
        )
    return findings


def detect_all(
    snapshot: FixtureQualitySnapshot,
    *,
    now: datetime | None = None,
) -> list[QualityFinding]:
    """Applica tutte le regole su uno snapshot fixture."""
    return [
        *detect_missing(snapshot),
        *detect_delays(snapshot, now=now),
        *detect_conflicts(snapshot),
        *detect_corrections(snapshot),
    ]


def validate_retry_target(*, fixture_provider_id: int | None) -> None:
    """Validazione lato server per rilancio sync."""
    if fixture_provider_id is None or fixture_provider_id <= 0:
        msg = "Identificativo fixture provider non valido per il rilancio sync"
        raise ValueError(msg)
