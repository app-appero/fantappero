"""Repository scan for accidental secret material in tracked files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*\S+"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*\S+"),
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+\S+"),
    re.compile(r"(?i)api[_-]?football[_-]?key\s*[:=]\s*['\"]?[a-z0-9]{20,}"),
    re.compile(r"(?i)apisports[_-]?key\s*[:=]\s*['\"]?[a-z0-9]{20,}"),
)

ALLOWLIST_SUFFIXES = (
    ".env.example",
    "configuration_and_secrets.md",
    # Test fixture with representative (non-real) redaction inputs.
    "backend/tests/unit/config/test_redaction.py",
    # API docs using the literal `<access_token>` placeholder, not a token.
    "docs/api/privacy.md",
    "docs/api/profile.md",
)

ALLOWLIST_PATH_PREFIXES = (
    "backend/tests/fixtures/",
    "docs/operations/configuration_and_secrets.md",
)


def _git_tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    paths: list[Path] = []
    for line in proc.stdout.splitlines():
        rel = line.strip()
        if not rel:
            continue
        path = REPO_ROOT / rel
        if path.is_file():
            paths.append(path)
    return paths


def _is_allowlisted(rel: str) -> bool:
    normalized = rel.replace("\\", "/")
    if any(normalized.endswith(suffix) for suffix in ALLOWLIST_SUFFIXES):
        return True
    return any(normalized.startswith(prefix) for prefix in ALLOWLIST_PATH_PREFIXES)


def test_no_secret_material_in_tracked_files() -> None:
    offenders: list[str] = []
    for path in _git_tracked_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if _is_allowlisted(rel):
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{rel} matches {pattern.pattern}")
    assert not offenders, "Potential secrets in tracked files:\n" + "\n".join(offenders)
