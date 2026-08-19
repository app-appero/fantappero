#!/usr/bin/env bash
# Automated smoke tests for the local Compose stack (EP01-02).
#
# Covers:
#   1) Service smoke (all essential healthy + API /health)
#   2) Restart + named-volume persistence (Postgres marker)
#   3) Explicit error when a required dependency is down
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-infra/local/.env.example}"
if [[ -f infra/local/.env ]]; then
  ENV_FILE="infra/local/.env"
fi

compose() {
  docker compose --env-file "$ENV_FILE" "$@"
}

PASS=0
FAIL=0

pass() {
  echo "PASS: $*"
  PASS=$((PASS + 1))
}

fail() {
  echo "FAIL: $*" >&2
  FAIL=$((FAIL + 1))
}

cleanup() {
  compose start postgres redis >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== EP01-02 local stack smoke =="

# --- 1) Smoke: healthy essentials ---
if "${ROOT}/infra/scripts/dev_healthcheck.sh"; then
  pass "essential services healthy"
else
  fail "essential services not healthy (start with ./infra/scripts/dev_up.sh)"
  echo "Summary: ${PASS} passed, ${FAIL} failed"
  exit 1
fi

MARKER="fantappero_smoke_$(date +%s)"
PG_USER="${POSTGRES_USER:-fantappero}"
PG_DB="${POSTGRES_DB:-fantappero}"

# --- 2) Persistence across restart ---
if compose exec -T postgres \
  psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 \
  -c "CREATE TABLE IF NOT EXISTS _ep01_smoke (id text PRIMARY KEY);" \
  -c "INSERT INTO _ep01_smoke(id) VALUES ('${MARKER}') ON CONFLICT DO NOTHING;" \
  >/dev/null; then
  compose restart postgres >/dev/null
  # wait until healthy again
  for _ in $(seq 1 30); do
    st="$(compose ps --format '{{.Service}} {{.Health}}' | awk '$1=="postgres"{print $2}')"
    [[ "$st" == "healthy" ]] && break
    sleep 2
  done
  if compose exec -T postgres \
    psql -U "$PG_USER" -d "$PG_DB" -tAc \
    "SELECT 1 FROM _ep01_smoke WHERE id='${MARKER}'" | grep -q 1; then
    pass "postgres data persisted across restart (volume fantappero_pg_data)"
  else
    fail "postgres marker missing after restart"
  fi
  compose exec -T postgres \
    psql -U "$PG_USER" -d "$PG_DB" -c "DELETE FROM _ep01_smoke WHERE id='${MARKER}';" \
    >/dev/null || true
else
  fail "could not write postgres smoke marker"
fi

# Redis AOF volume: set key, restart, check
if compose exec -T redis redis-cli SET "ep01:smoke:${MARKER}" "1" >/dev/null; then
  compose restart redis >/dev/null
  for _ in $(seq 1 30); do
    st="$(compose ps --format '{{.Service}} {{.Health}}' | awk '$1=="redis"{print $2}')"
    [[ "$st" == "healthy" ]] && break
    sleep 2
  done
  # give AOF a moment after restart
  sleep 2
  val="$(compose exec -T redis redis-cli GET "ep01:smoke:${MARKER}" | tr -d '\r')"
  if [[ "$val" == "1" ]]; then
    pass "redis data persisted across restart (volume fantappero_redis_data)"
  else
    fail "redis key missing after restart (got: ${val})"
  fi
  compose exec -T redis redis-cli DEL "ep01:smoke:${MARKER}" >/dev/null || true
else
  fail "could not write redis smoke key"
fi

# --- 3) Explicit error when dependency missing ---
compose stop postgres >/dev/null
sleep 3
# API should flip to unhealthy /health 503 once probes fail
api_bad=0
for _ in $(seq 1 30); do
  code="$(compose exec -T api curl -s -o /tmp/health.json -w '%{http_code}' \
    http://127.0.0.1:8001/health 2>/dev/null | tr -d '\r' || true)"
  code="${code:-000}"
  # curl -w appends after body when -o is used; keep last 3 digits if noisy
  code="${code: -3}"
  if [[ "$code" == "503" ]]; then
    api_bad=1
    break
  fi
  sleep 2
done
compose start postgres >/dev/null

if (( api_bad == 1 )); then
  pass "API returns 503 when postgres dependency is down"
else
  fail "expected API /health 503 while postgres stopped"
fi

# wait for recovery
HEALTH_TIMEOUT_SEC=120 "${ROOT}/infra/scripts/dev_healthcheck.sh" >/dev/null \
  && pass "stack recovered after postgres restart" \
  || fail "stack did not recover after postgres restart"

# Reset without CONFIRM must fail
if CONFIRM= ./infra/scripts/dev_reset.sh >/dev/null 2>&1; then
  fail "dev_reset.sh should refuse without CONFIRM=yes"
else
  pass "dev_reset.sh refuses without CONFIRM=yes"
fi

echo
echo "Summary: ${PASS} passed, ${FAIL} failed"
if (( FAIL > 0 )); then
  exit 1
fi
