"""Load key/value pairs from a local .env file without overriding existing env."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def load_repo_dotenv(repo_root: Path | None = None) -> None:
    root = repo_root or Path(__file__).resolve().parents[4]
    load_dotenv_file(root / ".env")
