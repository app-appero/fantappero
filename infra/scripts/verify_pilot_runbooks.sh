#!/usr/bin/env bash
# EP12-06 runbook simulations against disposable/test-only resources.

set -euo pipefail

if [[ "${OSTYPE:-}" == msys* ]]; then
  export MSYS_NO_PATHCONV=1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

env_file="${ENV_FILE:-infra/local/.env.example}"
compose=(docker compose --env-file "$env_file")
test_database_url='postgresql://fantappero:fantappero_local_dev_only@postgres-test:5432/fantappero_test'
test_redis_url='redis://redis-perf:6379/0'
perf_database_url='postgresql://fantappero_perf:fantappero_perf_local_only@postgres-perf:5432/fantappero_performance'
run_id="$(date -u +%Y%m%dT%H%M%SZ)"
backup_rel="./artifacts/runbook-dr/$run_id"
backup_abs="$repo_root/artifacts/runbook-dr/$run_id"
export POSTGRES_BACKUP_HOST_PATH="$backup_rel"

cleanup() {
  status="$1"
  trap - EXIT INT TERM
  # Remove only the fixed restore target from the test PostgreSQL service.
  # postgres-test itself stays available for the normal integration suite.
  "${compose[@]}" --profile test exec -T postgres-test \
    dropdb --if-exists --force -U fantappero fantappero_restore_ep12 \
    >/dev/null 2>&1 || true
  # Exact, disposable service allowlist.  Never stop/remove postgres, redis,
  # api, worker or any pilot/dev service.
  "${compose[@]}" --profile performance --profile backup-test rm -sf \
    api-restore-test postgres-perf redis-perf >/dev/null 2>&1 || true
  exit "$status"
}
trap 'cleanup $?' EXIT
trap 'cleanup 130' INT
trap 'cleanup 143' TERM

run_integration() {
  scenario="$1"
  shift
  printf 'EP12-06 scenario=%s resource=postgres-test\n' "$scenario"
  "${compose[@]}" --profile test --profile performance run --rm --no-deps \
    -e FANTAPPERO_ENV=test \
    -e DATABASE_URL="$test_database_url" \
    -e REDIS_URL="$test_redis_url" \
    api python -m pytest "$@" -ra --tb=short
}

printf 'EP12-06: build current backend and start isolated dependencies\n'
"${compose[@]}" build api
"${compose[@]}" --profile test --profile performance up -d postgres-test redis-perf

run_integration sports-data \
  tests/integration/sports_data/test_quality_panel.py::test_quality_scan_detects_missing_and_is_idempotent \
  tests/integration/sports_data/test_quality_panel.py::test_retry_sync_offline_idempotent_and_resolves_gap

run_integration homologated-round \
  tests/integration/leagues/test_scoring_service.py::test_homologate_round_locks_data_and_correction_reopens_it

run_integration security-incident \
  tests/integration/authorization/test_cross_league.py::test_cross_league_view_denied \
  tests/integration/authorization/test_cross_league.py::test_cross_league_admin_panel_denied_for_member \
  tests/integration/leagues/test_audit_log.py::test_league_admin_sees_own_league_audit_events \
  tests/integration/leagues/test_audit_log.py::test_audit_log_denied_for_non_member

run_integration market-error \
  tests/integration/market/test_trade_proposal.py::test_concurrent_cancel_attempts_only_one_succeeds \
  tests/integration/market/test_trade_decision.py::test_accept_swaps_players_and_credits_atomically

printf 'EP12-06 scenario=data-loss source=postgres-perf target=postgres-test\n'
# Recreate only the disposable performance services so the source is known and
# independent from the dev/pilot database.
"${compose[@]}" --profile performance rm -sf postgres-perf redis-perf >/dev/null 2>&1 || true
"${compose[@]}" --profile performance up -d postgres-perf redis-perf
"${compose[@]}" --profile performance run --rm --no-deps performance-seed \
  python -m alembic upgrade head
"${compose[@]}" --profile performance run --rm --no-deps performance-seed \
  python -m devtools.seed_performance_scenario --users 1 --output /tmp/ep12-06-seed.json

mkdir -p "$backup_abs"
"${compose[@]}" --profile backup --profile performance run --rm --no-deps \
  -e PGHOST=postgres-perf \
  -e PGPORT=5432 \
  -e PGUSER=fantappero_perf \
  -e PGPASSWORD=fantappero_perf_local_only \
  -e PGDATABASE=fantappero_performance \
  -e AVATAR_SOURCE=/tmp/empty-avatars \
  --entrypoint /bin/sh postgres-backup \
  -c 'mkdir -p /tmp/empty-avatars && /scripts/backup_postgres.sh'

"${compose[@]}" --profile backup-test run --rm --no-deps postgres-restore-test
"${compose[@]}" --profile backup-test run --rm --no-deps \
  -e SOURCE_DATABASE_URL="$perf_database_url" \
  api-restore-test python scripts/verify_restored_database.py --minimum-rows 100
"${compose[@]}" --profile backup-test run --rm --no-deps avatar-restore-test

"${compose[@]}" --profile backup-test --profile performance run --rm --no-deps \
  -e REDIS_URL="$test_redis_url" \
  api-restore-test python -c \
  'from fastapi.testclient import TestClient; from app.main import app; response = TestClient(app).get("/ready"); assert response.status_code == 200 and response.json()["status"] == "ok", response.text'

printf 'EP12-06: PASS all five scenarios; disposable backup=%s\n' "$backup_rel"
