"""Offline sports dataset tests — no external network."""

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = BACKEND_ROOT / "scripts" / "validate_sports_dataset.py"
DATASET = BACKEND_ROOT / "tests" / "fixtures" / "api_football"


def test_validate_sports_dataset_offline():
    assert DATASET.is_dir()
    assert (DATASET / "manifest.json").is_file()
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), "--root", str(DATASET)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_manifest_has_twenty_fixtures_and_five_leagues():
    import json

    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    fixtures = manifest["fixtures"]
    assert len(fixtures) >= 20
    leagues = {int(f["league_id"]) for f in fixtures}
    assert leagues == {39, 140, 135, 78, 61}


def test_no_secret_material_in_dataset_files():
    import re

    patterns = [
        re.compile(r"(?i)x-apisports-key\s*[:=]\s*\S+"),
        re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*\S+"),
        re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+\S+"),
        re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-z0-9]{20,}"),
    ]
    for path in DATASET.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            assert not pat.search(text), f"{path} matches {pat.pattern}"
