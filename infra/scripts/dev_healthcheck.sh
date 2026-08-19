#!/usr/bin/env bash
# Verify essential local services are healthy (EP01-02).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-infra/local/.env.example}"
if [[ -f infra/local/.env ]]; then
  ENV_FILE="infra/local/.env"
fi

ESSENTIAL=(postgres redis api worker web)
TIMEOUT_SEC="${HEALTH_TIMEOUT_SEC:-180}"
SLEEP_SEC=3
deadline=$((SECONDS + TIMEOUT_SEC))

compose() {
  docker compose --env-file "$ENV_FILE" "$@"
}

fail() {
  echo "ERROR: $*" >&2
  compose ps || true
  exit 1
}

# Fail fast if Docker / Compose unavailable
if ! command -v docker >/dev/null 2>&1; then
  fail "docker not found — install Docker Desktop / Engine first"
fi
if ! docker info >/dev/null 2>&1; then
  fail "docker daemon not reachable"
fi
if ! compose version >/dev/null 2>&1; then
  fail "docker compose plugin not available"
fi

# Explicit missing-dependency check: compose project must exist with essentials
if ! compose ps --services >/dev/null 2>&1; then
  fail "compose project not available (run ./infra/scripts/dev_up.sh first)"
fi

echo "Checking essential services: ${ESSENTIAL[*]} (timeout ${TIMEOUT_SEC}s)"

while (( SECONDS < deadline )); do
  all_ok=1
  for svc in "${ESSENTIAL[@]}"; do
    status="$(compose ps --format '{{.Service}} {{.Health}} {{.State}}' \
      | awk -v s="$svc" '$1 == s { print $2; found=1 } END { if (!found) print "missing" }')"
    # Some compose versions leave Health empty when not healthy yet
    if [[ -z "$status" ]]; then
      status="starting"
    fi
    if [[ "$status" != "healthy" ]]; then
      all_ok=0
      echo "  - ${svc}: ${status}"
    else
      echo "  - ${svc}: healthy"
    fi
  done
  if (( all_ok == 1 )); then
    echo "All essential services healthy."
    # Extra smoke: API JSON
    api_port="$(compose port api 8001 2>/dev/null | awk -F: '{print $NF}' || true)"
    api_port="${api_port:-8001}"
    if command -v curl >/dev/null 2>&1; then
      body="$(curl -fsS "http://127.0.0.1:${api_port}/health" || true)"
      echo "API /health => ${body}"
      echo "$body" | grep -q '"status":"ok"' || fail "API /health did not return status ok"
    fi
    compose ps
    exit 0
  fi
  sleep "$SLEEP_SEC"
done

fail "timed out waiting for healthy services after ${TIMEOUT_SEC}s"
