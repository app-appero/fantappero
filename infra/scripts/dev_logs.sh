#!/usr/bin/env bash
# Tail logs for local stack services.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-infra/local/.env.example}"
if [[ -f infra/local/.env ]]; then
  ENV_FILE="infra/local/.env"
fi

SERVICES=("$@")
if [[ ${#SERVICES[@]} -eq 0 ]]; then
  SERVICES=(postgres redis api worker)
fi

docker compose --env-file "$ENV_FILE" logs -f --tail=100 "${SERVICES[@]}"
