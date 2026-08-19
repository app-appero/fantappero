#!/usr/bin/env bash
# Stop local stack containers (volumes preserved).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-infra/local/.env.example}"
if [[ -f infra/local/.env ]]; then
  ENV_FILE="infra/local/.env"
fi

docker compose --env-file "$ENV_FILE" stop "$@"
echo "Local stack stopped (named volumes kept)."
