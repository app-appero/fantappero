"""Report emitters: markdown summary helpers and CSV rows."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Iterable

from .calculator import SimulationReport


CSV_FIELDS = [
    "scenario",
    "daily_requests",
    "monthly_requests",
    "peak_rpm",
    "matches_pre",
    "matches_live",
    "matches_post",
    "matches_late",
    "leagues_active",
    "max_concurrent_live",
    "fantasy_users",
    "catalog",
    "pre_match",
    "live",
    "post_match",
    "late_corrections",
    "recommended_plan",
    "minimum_daily_quota",
    "operational_margin",
    "assumptions_fingerprint",
]


def scenario_rows(report: SimulationReport) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, result in report.scenarios.items():
        rows.append(
            {
                "scenario": name,
                "daily_requests": round(result.daily_requests, 2),
                "monthly_requests": round(result.monthly_requests, 2),
                "peak_rpm": round(result.peak_rpm, 2),
                "matches_pre": result.matches["pre"],
                "matches_live": result.matches["live"],
                "matches_post": result.matches["post"],
                "matches_late": result.matches["late"],
                "leagues_active": result.matches["leagues_active"],
                "max_concurrent_live": result.matches["max_concurrent_live"],
                "fantasy_users": result.fantasy_users,
                "catalog": round(result.by_bucket.get("catalog", 0.0), 2),
                "pre_match": round(result.by_bucket.get("pre_match", 0.0), 2),
                "live": round(result.by_bucket.get("live", 0.0), 2),
                "post_match": round(result.by_bucket.get("post_match", 0.0), 2),
                "late_corrections": round(
                    result.by_bucket.get("late_corrections", 0.0), 2
                ),
                "recommended_plan": report.recommendation.recommended_plan,
                "minimum_daily_quota": report.recommendation.minimum_daily_quota,
                "operational_margin": report.recommendation.operational_margin,
                "assumptions_fingerprint": report.assumptions_fingerprint,
            }
        )
    return rows


def render_csv(report: SimulationReport) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in scenario_rows(report):
        writer.writerow(row)
    return buffer.getvalue()


def write_csv(report: SimulationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_csv(report), encoding="utf-8")


def render_text_report(report: SimulationReport) -> str:
    rec = report.recommendation
    lines = [
        f"API quota simulation (EP00-04) v{report.version}",
        f"assumptions_fingerprint={report.assumptions_fingerprint}",
        "",
        "Scenarios (daily / monthly requests):",
    ]
    for name, result in report.scenarios.items():
        lines.append(
            f"  - {name}: {result.daily_requests:.0f} / day, "
            f"{result.monthly_requests:.0f} / month, peak_rpm={result.peak_rpm:.1f}"
        )
    lines.extend(
        [
            "",
            "Recommendation:",
            f"  sizing basis daily (peak): {rec.sizing_basis_daily:.0f}",
            f"  operational margin: {rec.operational_margin:.0%}",
            f"  minimum daily quota: {rec.minimum_daily_quota}",
            f"  recommended plan: {rec.recommended_plan} "
            f"({rec.recommended_daily_limit}/day, {rec.recommended_rpm_limit} rpm)",
            f"  peak rpm: {rec.peak_rpm:.1f} (budget need >= {rec.rpm_budget:.1f}) "
            f"rpm_ok={rec.rpm_ok}",
            "",
            "Quota near exhaustion:",
        ]
    )
    policy = report.quota_exhaustion_policy
    lines.append(
        f"  warn<={policy['warn_remaining_fraction']:.0%} remaining; "
        f"degrade<={policy['degrade_remaining_fraction']:.0%}; "
        f"critical_only<={policy['critical_only_remaining_fraction']:.0%}"
    )
    return "\n".join(lines) + "\n"


def write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")
