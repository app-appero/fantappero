#!/usr/bin/env bash
# EP12-03 smoke/full capacity run against disposable postgres-perf/redis-perf.

set -euo pipefail

# Git Bash on Windows otherwise rewrites container paths such as /artifacts
# into C:/Program Files/Git/artifacts before Docker receives them.
export MSYS_NO_PATHCONV=1

mode="${1:-full}"
if [[ "$mode" != "smoke" && "$mode" != "full" ]]; then
  echo "Usage: $0 [smoke|full]" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

artifact_root="$repo_root/artifacts/performance"
runtime_dir="$artifact_root/runtime"
result_dir="$artifact_root/results"
mkdir -p "$runtime_dir" "$result_dir"

# Do not mix a new run with stale PASS/FAIL evidence from an earlier attempt.
# Keep the allowlist explicit because artifacts may contain unrelated cards.
rm -f \
  "$result_dir/compose-failure.log" \
  "$result_dir/smoke-summary.json" \
  "$result_dir/steady-summary.json" \
  "$result_dir/spike-summary.json" \
  "$result_dir/smoke-resources.tsv" \
  "$result_dir/steady-resources.tsv" \
  "$result_dir/spike-resources.tsv" \
  "$result_dir/api-metrics.prom" \
  "$result_dir/postgres-summary.json" \
  "$result_dir/redis-queue-depth.txt" \
  "$result_dir/worker-inspect.txt" \
  "$result_dir/worker-ping-summary.json" \
  "$result_dir/worker-domain-summary.json" \
  "$result_dir/worker-live-disabled-summary.json"

compose=(docker compose --profile performance)
perf_services=(api-perf worker-perf postgres-perf redis-perf)
sampler_pid=""

cleanup() {
  status="$1"
  trap - EXIT INT TERM
  if [[ -n "$sampler_pid" ]]; then
    kill "$sampler_pid" >/dev/null 2>&1 || true
    wait "$sampler_pid" >/dev/null 2>&1 || true
  fi
  if [[ "$status" -ne 0 ]]; then
    "${compose[@]}" logs --no-color --tail=250 "${perf_services[@]}" \
      >"$result_dir/compose-failure.log" 2>&1 || true
  fi
  if [[ "${PERF_KEEP_STACK:-0}" != "1" ]]; then
    # Exact service allowlist only: never stop/remove the ordinary dev stack.
    "${compose[@]}" rm -sf "${perf_services[@]}" >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap 'cleanup $?' EXIT
trap 'cleanup 130' INT
trap 'cleanup 143' TERM

# A new postgres-perf container means a new tmpfs database every run.  Remove
# only the four isolated services, even when a previous run was interrupted.
"${compose[@]}" rm -sf "${perf_services[@]}" >/dev/null 2>&1 || true
"${compose[@]}" build api-perf
"${compose[@]}" up -d postgres-perf redis-perf
"${compose[@]}" run --rm performance-seed python -m alembic upgrade head
"${compose[@]}" up -d api-perf worker-perf

for _attempt in $(seq 1 60); do
  api_status="$(docker inspect -f '{{.State.Health.Status}}' fantappero-api-perf 2>/dev/null || true)"
  worker_status="$(docker inspect -f '{{.State.Health.Status}}' fantappero-worker-perf 2>/dev/null || true)"
  if [[ "$api_status" == "healthy" && "$worker_status" == "healthy" ]]; then
    break
  fi
  sleep 2
done
if [[ "${api_status:-}" != "healthy" || "${worker_status:-}" != "healthy" ]]; then
  echo "Performance stack did not become healthy (api=$api_status worker=$worker_status)." >&2
  exit 1
fi

user_count="${PERF_USER_COUNT:-20}"
"${compose[@]}" run --rm performance-seed \
  python -m devtools.seed_performance_scenario \
  --users "$user_count" \
  --output /artifacts/runtime/seed.json

"${compose[@]}" run --rm performance-seed \
  python scripts/benchmark_celery.py \
  --task app.worker.ping --count 100 --p95-ms 1000 \
  --output /artifacts/results/worker-ping-summary.json
"${compose[@]}" run --rm performance-seed \
  python scripts/benchmark_celery.py \
  --task fantasy_turns.ensure_upcoming --count 20 --p95-ms 5000 \
  --output /artifacts/results/worker-domain-summary.json
"${compose[@]}" run --rm performance-seed \
  python scripts/benchmark_celery.py \
  --task sports_data.poll_live_window --count 1 --p95-ms 5000 \
  --output /artifacts/results/worker-live-disabled-summary.json

sample_resources() {
  while true; do
    timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    for container in fantappero-api-perf fantappero-postgres-perf fantappero-worker-perf; do
      docker stats --no-stream \
        --format "$timestamp\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}" \
        "$container" 2>/dev/null || true
    done
    sleep 2
  done
}

run_k6() {
  test_type="$1"
  sample_resources >"$result_dir/${test_type}-resources.tsv" &
  sampler_pid=$!
  set +e
  "${compose[@]}" run --rm -e PERF_TEST_TYPE="$test_type" \
    k6 run /scripts/critical_flow.js
  k6_status=$?
  set -e
  kill "$sampler_pid" >/dev/null 2>&1 || true
  wait "$sampler_pid" >/dev/null 2>&1 || true
  sampler_pid=""
  return "$k6_status"
}

run_k6 smoke
if [[ "$mode" == "full" ]]; then
  run_k6 steady
  run_k6 spike
fi

"${compose[@]}" exec -T api-perf curl -fsS http://127.0.0.1:8001/metrics \
  >"$result_dir/api-metrics.prom"
"${compose[@]}" exec -T redis-perf redis-cli --raw llen celery \
  >"$result_dir/redis-queue-depth.txt"
"${compose[@]}" exec -T postgres-perf psql -U fantappero_perf -d fantappero_performance \
  -Atc "SELECT json_build_object(
    'database', datname,
    'numBackends', numbackends,
    'transactionsCommitted', xact_commit,
    'transactionsRolledBack', xact_rollback,
    'blocksRead', blks_read,
    'blocksHit', blks_hit,
    'temporaryFiles', temp_files,
    'deadlocks', deadlocks,
    'databaseBytes', pg_database_size(datname)
  ) FROM pg_stat_database WHERE datname = current_database();" \
  >"$result_dir/postgres-summary.json"
"${compose[@]}" exec -T worker-perf celery -A app.worker.celery_app inspect ping \
  >"$result_dir/worker-inspect.txt"

echo "EP12-03 $mode completed; evidence under $result_dir"
