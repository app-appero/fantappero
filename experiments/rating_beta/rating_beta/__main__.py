"""CLI: run Rating Beta offline on the EP00-02 corpus and emit a markdown report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_REPORT_PATH,
    REPO_ROOT,
    load_formula_config,
)
from .corpus import DEFAULT_CORPUS, load_corpus_ratings
from .report import build_role_stats, render_markdown_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FantApperò Rating Beta offline experiment (EP00-05). No DB writes."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to versioned formula YAML",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help="Root of offline api_football corpus",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Markdown report output path",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional JSON dump of all rating results (diagnostic only)",
    )
    args = parser.parse_args(argv)

    config = load_formula_config(args.config)
    results = load_corpus_ratings(config, corpus_root=args.corpus)
    role_stats = build_role_stats(results)
    report = render_markdown_report(
        config=config,
        role_stats=role_stats,
        results=results,
        corpus_note=str(args.corpus.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
        if args.corpus.resolve().is_relative_to(REPO_ROOT)
        else str(args.corpus),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8", newline="\n")
    print(f"wrote {args.report} ({len(results)} player rows, version={config.version})")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = [r.as_dict() for r in results]
        args.json_out.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
