#!/usr/bin/env python3
"""Validate the offline API-Football dataset (no network calls).

Usage:
  python backend/scripts/validate_sports_dataset.py
  python backend/scripts/validate_sports_dataset.py --root backend/tests/fixtures/api_football
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = BACKEND_ROOT / "tests" / "fixtures" / "api_football"
REQUIRED_LEAGUES = {39, 140, 135, 78, 61}
REQUIRED_MATCH_ENDPOINTS = {
    "/fixtures": "fixtures.json",
    "/fixtures/events": "fixtures_events.json",
    "/fixtures/lineups": "fixtures_lineups.json",
    "/fixtures/players": "fixtures_players.json",
}
RARE_CASES = {
    "penalty_scored",
    "penalty_missed",
    "penalty_saved",
    "red_card",
    "substitution",
    "clean_sheet",
    "own_goal",
    "postponement",
    "post_match_correction",
}
SECRET_PATTERNS = [
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*\S+"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*\S+"),
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+\S+"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-z0-9]{20,}"),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_envelope(obj: dict[str, Any], endpoint: str, errors: list[str], path: str) -> None:
    for key in ("get", "parameters", "errors", "results", "paging", "response"):
        if key not in obj:
            errors.append(f"{path}: missing envelope key '{key}'")
    if obj.get("get") != endpoint.lstrip("/") and obj.get("get") != endpoint:
        # accept both "fixtures" and "/fixtures"
        got = str(obj.get("get", "")).lstrip("/")
        exp = endpoint.lstrip("/")
        if got != exp:
            errors.append(f"{path}: get={obj.get('get')!r} expected {exp!r}")
    if not isinstance(obj.get("response"), list):
        errors.append(f"{path}: response must be a list")
    if not isinstance(obj.get("parameters"), dict):
        errors.append(f"{path}: parameters must be an object")


def validate(root: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    manifest_path = root / "manifest.json"
    checksums_path = root / "checksums.sha256"
    if not manifest_path.is_file():
        print(f"ERROR: missing {manifest_path}", file=sys.stderr)
        return 2
    if not checksums_path.is_file():
        print(f"ERROR: missing {checksums_path}", file=sys.stderr)
        return 2

    manifest = load_json(manifest_path)
    fixtures = manifest.get("fixtures") or []
    coverage = manifest.get("coverage") or {}
    files = manifest.get("files") or []

    if len(fixtures) < 20:
        errors.append(f"fixture_count={len(fixtures)} < 20")

    leagues = {int(f["league_id"]) for f in fixtures}
    missing_leagues = REQUIRED_LEAGUES - leagues
    if missing_leagues:
        errors.append(f"missing leagues: {sorted(missing_leagues)}")

    found = set((coverage.get("rare_cases_found") or {}).keys())
    not_found = set(coverage.get("rare_cases_not_found") or [])
    for tag in RARE_CASES:
        if tag not in found and tag not in not_found:
            errors.append(f"rare case '{tag}' neither found nor listed as not_found")

    expected_match_dirs = {
        (int(fx["league_id"]), int(fx["fixture_id"])) for fx in fixtures
    }

    # naming + endpoint files per match
    for fx in fixtures:
        fid = int(fx["fixture_id"])
        league_id = int(fx["league_id"])
        for endpoint, filename in REQUIRED_MATCH_ENDPOINTS.items():
            rel = f"matches/{league_id}/{fid}/{filename}"
            path = root / rel
            if not path.is_file():
                errors.append(f"missing file {rel}")
                continue
            if path.name != filename:
                errors.append(f"non-deterministic name for {rel}")
            try:
                obj = load_json(path)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON {rel}: {exc}")
                continue
            assert_envelope(obj, endpoint, errors, rel)
            # fixture id consistency
            if endpoint == "/fixtures":
                ids = [item.get("fixture", {}).get("id") for item in obj.get("response") or []]
                if fid not in ids:
                    errors.append(f"{rel}: fixture id {fid} not in payload")
            else:
                param_fid = (obj.get("parameters") or {}).get("fixture")
                if param_fid is not None and str(param_fid) != str(fid):
                    errors.append(f"{rel}: parameters.fixture={param_fid} != {fid}")

    matches_root = root / "matches"
    if matches_root.is_dir():
        for league_dir in matches_root.iterdir():
            if not league_dir.is_dir() or not league_dir.name.isdigit():
                continue
            for fx_dir in league_dir.iterdir():
                if not fx_dir.is_dir() or not fx_dir.name.isdigit():
                    continue
                key = (int(league_dir.name), int(fx_dir.name))
                if key not in expected_match_dirs:
                    errors.append(
                        f"orphan match dir not in manifest: matches/{key[0]}/{key[1]}"
                    )

    # checksum verification
    checksum_map: dict[str, str] = {}
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, rel = line.split(None, 1)
        checksum_map[rel.replace("\\", "/")] = digest

    for entry in files:
        rel = entry["path"].replace("\\", "/")
        path = root / rel
        if not path.is_file():
            errors.append(f"manifest file missing on disk: {rel}")
            continue
        actual = sha256_file(path)
        expected = entry.get("sha256")
        if expected and actual != expected:
            errors.append(f"checksum mismatch for {rel}: manifest={expected} actual={actual}")
        if rel in checksum_map and checksum_map[rel] != actual:
            errors.append(f"checksums.sha256 mismatch for {rel}")

    if "manifest.json" in checksum_map:
        actual_manifest = sha256_file(manifest_path)
        if checksum_map["manifest.json"] != actual_manifest:
            errors.append("checksums.sha256 mismatch for manifest.json")

    # secret scan on all JSON under root
    for path in root.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                errors.append(f"secret-like pattern in {path.relative_to(root).as_posix()}: {pat.pattern}")
                break
        # headers object should not appear
        if re.search(r'(?i)"headers"\s*:\s*\{', text):
            errors.append(f"headers object present in {path.relative_to(root).as_posix()}")

    # no network helpers accidentally imported by this module during validation
    # (documented guarantee; this script itself performs zero HTTP)

    if errors:
        print("VALIDATION FAILED")
        for e in errors:
            print(f" - {e}")
        return 1

    print("VALIDATION OK")
    print(f" fixtures: {len(fixtures)}")
    print(f" leagues: {sorted(leagues)}")
    print(f" rare found: {sorted(found)}")
    print(f" rare not_found: {sorted(not_found)}")
    if warnings:
        for w in warnings:
            print(f" warning: {w}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_DATASET,
    )
    args = parser.parse_args()
    raise SystemExit(validate(args.root.resolve()))


if __name__ == "__main__":
    main()
