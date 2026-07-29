#!/usr/bin/env bash
# Apply Alembic migrations via Compose network (avoids host DATABASE_URL / port 5432 issues).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-infra/local/.env.example}"
if [[ -f infra/local/.env ]]; then
  ENV_FILE="infra/local/.env"
fi

if ! docker ps --filter "name=fantappero-postgres" --filter "status=running" -q | grep -q .; then
  echo "fantappero-postgres is not running." >&2
  echo "Start the stack: docker compose --env-file infra/local/.env.example up -d --build" >&2
  exit 1
fi

ALEMBIC_ARGS=("$@")
if [[ ${#ALEMBIC_ARGS[@]} -eq 0 ]]; then
  ALEMBIC_ARGS=(upgrade head)
fi

echo "Running alembic ${ALEMBIC_ARGS[*]} (env: ${ENV_FILE}) ..."
docker compose --env-file "$ENV_FILE" run --rm --no-deps api python -m alembic "${ALEMBIC_ARGS[@]}"
echo "Migrations applied."
