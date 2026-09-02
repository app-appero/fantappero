"""CLI: python -m api_quota_estimator [--config PATH] [--csv PATH]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .calculator import QuotaCalculator
from .config import DEFAULT_CONFIG_PATH, load_config, with_overrides
from .report import render_text_report, write_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate API-Football request volume (EP00-04)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to JSON assumptions (default: config/default.json)",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        metavar="JSON",
        help='Deep-merge JSON object into config, e.g. \'{"fantasy_users":1}\'',
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Write scenario summary CSV to this path",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Write full machine-readable report JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    for raw in args.override:
        config = with_overrides(config, json.loads(raw))

    report = QuotaCalculator(config).simulate()
    sys.stdout.write(render_text_report(report))

    if args.csv:
        write_csv(report, args.csv)
        sys.stdout.write(f"wrote CSV: {args.csv}\n")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": report.version,
            "assumptions_fingerprint": report.assumptions_fingerprint,
            "recommendation": report.recommendation.__dict__,
            "scenarios": {
                name: {
                    "daily_requests": r.daily_requests,
                    "monthly_requests": r.monthly_requests,
                    "peak_rpm": r.peak_rpm,
                    "by_bucket": r.by_bucket,
                    "matches": r.matches,
                    "fantasy_users": r.fantasy_users,
                    "notes": list(r.notes),
                }
                for name, r in report.scenarios.items()
            },
            "quota_exhaustion_policy": report.quota_exhaustion_policy,
            "resilience": report.resilience,
        }
        args.json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        sys.stdout.write(f"wrote JSON: {args.json}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
