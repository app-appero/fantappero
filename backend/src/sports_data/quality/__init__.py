"""Pannello qualità dati sportivi — scan, issue e rilancio sync (EP04-07)."""

from sports_data.quality.models import SportsDataQualityIssue, SportsDataSyncRetry
from sports_data.quality.retry import (
    QualityRetryError,
    create_retry_audit,
    run_retry,
    sync_single_fixture_offline,
    sync_single_fixture_with_client,
)
from sports_data.quality.rules import (
    FixtureQualitySnapshot,
    QualityFinding,
    detect_all,
    detect_conflicts,
    detect_corrections,
    detect_delays,
    detect_missing,
    validate_retry_target,
)
from sports_data.quality.scan import (
    QUALITY_OPEN_ISSUES,
    QUALITY_SCAN_DURATION_SECONDS,
    QUALITY_SCAN_ISSUES_TOTAL,
    QUALITY_SCAN_RUNS_TOTAL,
    quality_summary,
    scan_quality,
)
from sports_data.quality.types import (
    QualityIssueCode,
    QualityIssueKind,
    QualityIssueStatus,
    QualitySeverity,
    SyncRetryStatus,
)

__all__ = [
    "QUALITY_OPEN_ISSUES",
    "QUALITY_SCAN_DURATION_SECONDS",
    "QUALITY_SCAN_ISSUES_TOTAL",
    "QUALITY_SCAN_RUNS_TOTAL",
    "FixtureQualitySnapshot",
    "QualityFinding",
    "QualityIssueCode",
    "QualityIssueKind",
    "QualityIssueStatus",
    "QualityRetryError",
    "QualitySeverity",
    "SportsDataQualityIssue",
    "SportsDataSyncRetry",
    "SyncRetryStatus",
    "create_retry_audit",
    "detect_all",
    "detect_conflicts",
    "detect_corrections",
    "detect_delays",
    "detect_missing",
    "quality_summary",
    "run_retry",
    "scan_quality",
    "sync_single_fixture_offline",
    "sync_single_fixture_with_client",
    "validate_retry_target",
]
