"""Schema drift verification (wraps ``alembic check``)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=BACKEND,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        print("OK: schema matches models (no drift)")
        return 0
    print("ERROR: schema drift detected — run `alembic revision --autogenerate` to inspect", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
