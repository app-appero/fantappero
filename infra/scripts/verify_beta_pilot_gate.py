"""Validate the versioned EP12-07 package and its synthetic tabletop dataset."""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESS = ROOT / "docs/operations/beta_pilot_gate.md"
CARD = ROOT / "docs/operations/beta_readiness/ep12-07_pilot_gate_beta.md"
INDEX = ROOT / "docs/operations/beta_readiness/README.md"
TEMPLATE_REGISTER = ROOT / "docs/operations/templates/ep12-07_pilot_register.csv"
DECISION_TEMPLATE = ROOT / "docs/operations/templates/ep12-07_gate_decision.md"
DRY_RUN_REPORT = (
    ROOT / "docs/operations/evidence/ep12-07_internal_dry_run_2026-08-21.md"
)
DRY_RUN_REGISTER = (
    ROOT / "docs/operations/evidence/ep12-07_internal_dry_run_register_2026-08-21.csv"
)

REGISTER_FIELDS = [
    "observed_at_utc",
    "period_id",
    "league_alias",
    "kpi_id",
    "numerator",
    "denominator",
    "value",
    "unit",
    "source_type",
    "source_ref",
    "evidence_ref",
    "owner_role",
    "status",
    "notes_redacted",
]

KPI_IDS = {
    "ACTIVE_LEAGUES",
    "ACTIVE_PARTICIPANTS",
    "PILOT_DURATION_DAYS",
    "COMPLETED_ROUNDS",
    "CRITICAL_FLOW_COMPLETION",
    "CRITICAL_FLOW_BLOCKERS_OPEN",
    "SUPPORT_ACK_WITHIN_TARGET",
    "P0_INCIDENTS",
    "P1_OPEN_AT_GATE",
    "CAPACITY_RUN_PASS",
    "SECURITY_HIGH_CRITICAL",
    "BACKUP_MAX_INTERVAL_HOURS",
    "DR_DRILL_RESTORE_MINUTES",
    "ACTUAL_RECOVERY_RPO_HOURS",
    "ACTUAL_RECOVERY_RTO_MINUTES",
    "QUALITATIVE_SCORE",
    "RECOMMENDATION_INTENT",
}

SOURCE_TYPES = {
    "e2e",
    "k6",
    "ticket",
    "checkpoint",
    "security_review",
    "backup_log",
    "dr_drill",
    "survey",
}

REQUIRED_PACKAGE_MARKERS = {
    PROCESS: [
        "**il pilot reale non è stato eseguito e il gate Beta non è chiuso**",
        "## 1. Autorità e decisioni bloccanti",
        "## 3. Gate di ingresso prima degli inviti",
        "## 4. Onboarding e aspettative",
        "## 6. KPI, formule, sorgenti e soglie",
        "## 7. Decisione GO / NO-GO",
        "## 8. Dry-run interno ripetibile",
        "3–5 leghe",
        "almeno 28 giorni",
        "almeno 4 turni",
        "process-local",
    ],
    CARD: [
        "## Stato implementazione",
        "pilot reale",
        "beta_pilot_gate.md",
    ],
    INDEX: [
        "EP12-07",
        "pacchetto predisposto",
        "pilot reale",
    ],
    DECISION_TEMPLATE: [
        "## Esito (selezionare esattamente uno)",
        "**GO**",
        "**NO-GO**",
        "## Remediation NO-GO e retest",
        "`REQUIRED`",
    ],
    DRY_RUN_REPORT: [
        "tabletop deterministico",
        "primo caso NO-GO",
        "GO simulato",
        "non chiude",
    ],
}

MARKDOWN_LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
LEAGUE_ALIAS = re.compile(r"(?:ALL|PILOT-L\d{2})\Z")
EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?:password|secret|token|api[_-]?key)\s*[:=]\s*[^,\s]+", re.IGNORECASE
)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def read_csv(path: Path, errors: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or []), list(reader)
    except (OSError, csv.Error) as exc:
        fail(errors, f"cannot read CSV {path.relative_to(ROOT)}: {exc}")
        return [], []


def validate_required_files(errors: list[str]) -> None:
    for path, markers in REQUIRED_PACKAGE_MARKERS.items():
        if not path.is_file():
            fail(errors, f"missing required file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                fail(errors, f"{path.relative_to(ROOT)} missing marker: {marker}")

    if PROCESS.is_file() and DECISION_TEMPLATE.is_file():
        process_text = PROCESS.read_text(encoding="utf-8")
        decision_text = DECISION_TEMPLATE.read_text(encoding="utf-8")
        for kpi_id in KPI_IDS:
            if f"`{kpi_id}`" not in process_text:
                fail(errors, f"pilot process is missing KPI definition: {kpi_id}")
            if f"`{kpi_id}`" not in decision_text:
                fail(errors, f"decision template is missing KPI row: {kpi_id}")


def validate_links(errors: list[str]) -> int:
    checked = 0
    for path in REQUIRED_PACKAGE_MARKERS:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            file_part = target.split("#", maxsplit=1)[0]
            if not file_part:
                continue
            checked += 1
            resolved = (path.parent / file_part).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                fail(
                    errors,
                    f"link escapes repository in {path.relative_to(ROOT)}: {target}",
                )
                continue
            if not resolved.exists():
                fail(errors, f"broken link in {path.relative_to(ROOT)}: {target}")
    return checked


def validate_template_register(errors: list[str]) -> None:
    fields, rows = read_csv(TEMPLATE_REGISTER, errors)
    if fields != REGISTER_FIELDS:
        fail(errors, "pilot register template has an unexpected schema")
    if rows:
        fail(errors, "pilot register template must remain header-only")


def parse_number(
    row: dict[str, str], field: str, row_number: int, errors: list[str]
) -> float:
    try:
        return float(row[field])
    except (KeyError, TypeError, ValueError):
        fail(errors, f"dry-run row {row_number}: {field} must be numeric")
        return float("nan")


def validate_dry_run_register(errors: list[str]) -> list[dict[str, str]]:
    fields, rows = read_csv(DRY_RUN_REGISTER, errors)
    if fields != REGISTER_FIELDS:
        fail(errors, "dry-run register has an unexpected schema")
        return rows
    if len(rows) != 31:
        fail(errors, f"dry-run register must contain 31 rows, found {len(rows)}")

    raw = DRY_RUN_REGISTER.read_text(encoding="utf-8")
    for pattern, label in (
        (EMAIL, "email address"),
        (JWT, "JWT-like value"),
        (SENSITIVE_ASSIGNMENT, "secret-like assignment"),
    ):
        if pattern.search(raw):
            fail(errors, f"dry-run register contains a {label}")

    unique_keys: set[tuple[str, ...]] = set()
    for index, row in enumerate(rows, start=2):
        if set(row) != set(REGISTER_FIELDS) or any(
            not isinstance(value, str) for value in row.values()
        ):
            fail(errors, f"dry-run row {index}: malformed column count")
            continue
        if any(value.startswith(("=", "+", "-", "@")) for value in row.values()):
            fail(
                errors, f"dry-run row {index}: spreadsheet formula prefix is forbidden"
            )
        key = (
            row["observed_at_utc"],
            row["period_id"],
            row["league_alias"],
            row["kpi_id"],
            row["notes_redacted"],
        )
        if key in unique_keys:
            fail(errors, f"dry-run row {index}: duplicate observation key")
        unique_keys.add(key)

        try:
            timestamp = datetime.fromisoformat(
                row["observed_at_utc"].replace("Z", "+00:00")
            )
            if timestamp.tzinfo != timezone.utc:
                fail(errors, f"dry-run row {index}: timestamp must be UTC/Z")
        except ValueError:
            fail(errors, f"dry-run row {index}: invalid ISO timestamp")

        if not LEAGUE_ALIAS.fullmatch(row["league_alias"]):
            fail(errors, f"dry-run row {index}: unsafe league alias")
        if row["kpi_id"] not in KPI_IDS:
            fail(errors, f"dry-run row {index}: unknown KPI {row['kpi_id']}")
        if row["source_type"] not in SOURCE_TYPES:
            fail(
                errors, f"dry-run row {index}: unknown source type {row['source_type']}"
            )
        if not row["source_ref"].startswith("SIM-"):
            fail(errors, f"dry-run row {index}: source_ref is not explicitly synthetic")
        if not row["owner_role"] or len(row["notes_redacted"]) > 120:
            fail(errors, f"dry-run row {index}: owner or redacted note is invalid")

        evidence = (ROOT / row["evidence_ref"]).resolve()
        try:
            evidence.relative_to(ROOT)
        except ValueError:
            fail(errors, f"dry-run row {index}: evidence_ref escapes repository")
        else:
            if not evidence.is_file():
                fail(errors, f"dry-run row {index}: evidence_ref does not exist")

        if row["status"] == "not_applicable":
            if row["kpi_id"] not in {
                "ACTUAL_RECOVERY_RPO_HOURS",
                "ACTUAL_RECOVERY_RTO_MINUTES",
            }:
                fail(errors, f"dry-run row {index}: N/A is not allowed for this KPI")
            if any(row[field] for field in ("numerator", "denominator", "value")):
                fail(errors, f"dry-run row {index}: N/A KPI must not carry a value")
            if row["notes_redacted"] != "no-restore-simulated":
                fail(errors, f"dry-run row {index}: N/A recovery KPI lacks its reason")
            continue

        if row["status"] != "validated":
            fail(errors, f"dry-run row {index}: unsupported status {row['status']}")
            continue
        numerator = parse_number(row, "numerator", index, errors)
        denominator = parse_number(row, "denominator", index, errors)
        value = parse_number(row, "value", index, errors)
        if numerator < 0 or denominator < 0 or value < 0:
            fail(errors, f"dry-run row {index}: negative measurements are invalid")
        if row["unit"] in {"ratio", "score_1_5"} and denominator <= 0:
            fail(errors, f"dry-run row {index}: denominator must be positive")
        if row["unit"] in {"ratio", "score_1_5"} and denominator > 0:
            if abs(value - numerator / denominator) > 0.000001:
                fail(errors, f"dry-run row {index}: value does not match fraction")
    return rows


def one(
    rows: list[dict[str, str]],
    kpi_id: str,
    errors: list[str],
    *,
    alias: str = "ALL",
    note: str | None = None,
) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row["kpi_id"] == kpi_id
        and row["league_alias"] == alias
        and (note is None or row["notes_redacted"] == note)
    ]
    if len(matches) != 1:
        fail(
            errors,
            f"expected one {kpi_id}/{alias}/{note or '*'} row, found {len(matches)}",
        )
        return {field: "" for field in REGISTER_FIELDS}
    return matches[0]


def gate_value(row: dict[str, str]) -> float:
    try:
        return float(row["value"])
    except (TypeError, ValueError):
        return float("nan")


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        fail(errors, f"synthetic gate failed: {message}")


def evaluate_synthetic_gate(rows: list[dict[str, str]], errors: list[str]) -> None:
    active = one(rows, "ACTIVE_LEAGUES", errors)
    duration = one(rows, "PILOT_DURATION_DAYS", errors)
    require(errors, 3 <= gate_value(active) <= 5, "active leagues outside 3-5")
    require(errors, gate_value(duration) >= 28, "pilot duration below 28 days")

    league_aliases = sorted(
        {row["league_alias"] for row in rows if row["kpi_id"] == "COMPLETED_ROUNDS"}
    )
    require(
        errors, len(league_aliases) == int(gate_value(active)), "league count mismatch"
    )
    participant_total = one(rows, "ACTIVE_PARTICIPANTS", errors)
    participant_sum = 0.0
    for alias in league_aliases:
        participants = one(rows, "ACTIVE_PARTICIPANTS", errors, alias=alias)
        league_duration = one(rows, "PILOT_DURATION_DAYS", errors, alias=alias)
        rounds = one(rows, "COMPLETED_ROUNDS", errors, alias=alias)
        flow = one(rows, "CRITICAL_FLOW_COMPLETION", errors, alias=alias)
        participant_sum += gate_value(participants)
        require(
            errors, 6 <= gate_value(participants) <= 12, f"{alias} outside 6-12 users"
        )
        require(errors, gate_value(league_duration) >= 28, f"{alias} below 28 days")
        require(errors, gate_value(rounds) >= 4, f"{alias} has fewer than 4 rounds")
        require(errors, gate_value(flow) >= 0.8, f"{alias} flow completion below 80%")
    require(
        errors,
        gate_value(participant_total) == participant_sum,
        "aggregate participant count does not match leagues",
    )

    flow_all = one(rows, "CRITICAL_FLOW_COMPLETION", errors)
    require(errors, gate_value(flow_all) >= 0.9, "aggregate flow completion below 90%")
    require(
        errors,
        gate_value(one(rows, "CRITICAL_FLOW_BLOCKERS_OPEN", errors)) == 0,
        "critical blockers remain open",
    )
    support_all = one(rows, "SUPPORT_ACK_WITHIN_TARGET", errors, note="priority-all")
    support_critical = one(
        rows, "SUPPORT_ACK_WITHIN_TARGET", errors, note="priority-p0-p1"
    )
    require(
        errors,
        gate_value(support_all) >= 0.9,
        "overall support acknowledgement below 90%",
    )
    require(
        errors, gate_value(support_critical) == 1, "P0/P1 acknowledgement below 100%"
    )

    for zero_kpi in (
        "P0_INCIDENTS",
        "P1_OPEN_AT_GATE",
        "SECURITY_HIGH_CRITICAL",
    ):
        require(
            errors,
            gate_value(one(rows, zero_kpi, errors)) == 0,
            f"{zero_kpi} is non-zero",
        )

    for note in ("full-within-30-days", "smoke-within-7-days", "required-runs"):
        run = one(rows, "CAPACITY_RUN_PASS", errors, note=note)
        require(
            errors, gate_value(run) == 1, f"capacity requirement {note} did not pass"
        )

    require(
        errors,
        gate_value(one(rows, "BACKUP_MAX_INTERVAL_HOURS", errors)) <= 24,
        "backup interval exceeds RPO",
    )
    require(
        errors,
        gate_value(one(rows, "DR_DRILL_RESTORE_MINUTES", errors)) <= 30,
        "isolated restore exceeds the EP12-05 technical budget",
    )
    for recovery_kpi in ("ACTUAL_RECOVERY_RPO_HOURS", "ACTUAL_RECOVERY_RTO_MINUTES"):
        recovery = one(rows, recovery_kpi, errors)
        require(
            errors,
            recovery["status"] == "not_applicable",
            f"{recovery_kpi} lacks N/A reason",
        )

    require(
        errors,
        gate_value(one(rows, "QUALITATIVE_SCORE", errors)) >= 4,
        "qualitative score below 4/5",
    )
    require(
        errors,
        gate_value(one(rows, "RECOMMENDATION_INTENT", errors)) >= 0.8,
        "recommendation intent below 80%",
    )


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    links_checked = validate_links(errors)
    validate_template_register(errors)
    rows = validate_dry_run_register(errors)
    if rows:
        evaluate_synthetic_gate(rows, errors)
        missing_evidence_errors: list[str] = []
        missing_evidence_rows = [
            row
            for row in rows
            if not (
                row["kpi_id"] == "CAPACITY_RUN_PASS"
                and row["notes_redacted"] == "full-within-30-days"
            )
        ]
        evaluate_synthetic_gate(missing_evidence_rows, missing_evidence_errors)
        if not any("CAPACITY_RUN_PASS" in error for error in missing_evidence_errors):
            fail(errors, "missing-evidence self-test did not produce NO-GO")

    if errors:
        print("EP12-07 package: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("EP12-07 package: PASS")
    print(f"Links checked: PASS ({links_checked})")
    print("Template register: PASS (header only)")
    print(f"Dry-run register: PASS ({len(rows)} rows, privacy-safe schema)")
    print("Synthetic missing-evidence scenario: NO-GO (tabletop only)")
    print("Synthetic gate evaluation: GO (tabletop only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
