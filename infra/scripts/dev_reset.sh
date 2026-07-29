#!/usr/bin/env bash
# DESTRUCTIVE: stop stack and delete named volumes (Postgres + Redis data).
#
# Refuses unless CONFIRM=yes is set in the environment.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ "${CONFIRM:-}" != "yes" ]]; then
  cat <<'EOF' >&2
Refusing destructive reset.

This removes containers AND named volumes:
  - fantappero_pg_data
  - fantappero_redis_data
  - fantappero_web_node_modules
  - fantappero_web_app_node_modules
  - fantappero_web_contracts_node_modules
  - fantappero_web_ui_node_modules

Re-run explicitly:
  CONFIRM=yes ./infra/scripts/dev_reset.sh
  # or: make reset-local CONFIRM=yes
EOF
  exit 1
fi

ENV_FILE="${ENV_FILE:-infra/local/.env.example}"
if [[ -f infra/local/.env ]]; then
  ENV_FILE="infra/local/.env"
fi

echo "DESTRUCTIVE reset: removing containers and named volumes..."
docker compose --env-file "$ENV_FILE" down -v --remove-orphans
echo "Reset complete. Run ./infra/scripts/dev_up.sh (or make up) to recreate an empty stack."
