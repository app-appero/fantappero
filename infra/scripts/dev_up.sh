#!/usr/bin/env bash
# Start essential local stack (redis, api, worker, web; Postgres via remote DATABASE_URL).
# Optional local Postgres: docker compose --profile local-db up -d postgres
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-infra/local/.env.example}"
if [[ -f infra/local/.env ]]; then
  ENV_FILE="infra/local/.env"
fi

echo "Starting FantApperò local stack (env: ${ENV_FILE})..."
docker compose --env-file "$ENV_FILE" up -d --build "$@"
echo "Waiting for healthy services..."
"${ROOT}/infra/scripts/dev_healthcheck.sh"
