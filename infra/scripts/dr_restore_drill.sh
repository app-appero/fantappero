#!/usr/bin/env bash
# Repeatable EP12-05 restore drill. It never drops or restores the dev/pilot DB.

set -euo pipefail

# Git Bash rewrites container paths (for example /bin/sh) to Windows paths
# unless path conversion is disabled for Docker CLI arguments.
if [[ "${OSTYPE:-}" == msys* ]]; then
  export MSYS_NO_PATHCONV=1
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

ENV_FILE=${ENV_FILE:-infra/local/.env.example}
RESTORE_API_PORT=${RESTORE_API_PORT:-8003}
export RESTORE_API_PORT

compose=(docker compose --env-file "$ENV_FILE")

cleanup() {
  "${compose[@]}" --profile backup-test stop api-restore-test >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf 'DR drill: starting isolated dependencies\n'
"${compose[@]}" --profile test up -d postgres postgres-test redis mailpit

printf 'DR drill: creating a fresh backup (source is read-only to the backup job)\n'
"${compose[@]}" --profile backup run --rm --entrypoint /bin/sh \
  postgres-backup /scripts/backup_postgres.sh

printf 'DR drill: restoring to postgres-test/fantappero_restore_ep12\n'
"${compose[@]}" --profile backup-test run --rm postgres-restore-test

printf 'DR drill: verifying every table, row fingerprint and sequence\n'
"${compose[@]}" --profile backup-test run --rm --no-deps --entrypoint python \
  api-restore-test scripts/verify_restored_database.py --minimum-rows 100

printf 'DR drill: restoring avatars to an empty tmpfs staging path\n'
"${compose[@]}" --profile backup-test run --rm avatar-restore-test

printf 'DR drill: starting the API against the restored database\n'
"${compose[@]}" --profile backup-test up -d --force-recreate api-restore-test

ready=false
for _ in $(seq 1 24); do
  if curl -fsS "http://127.0.0.1:${RESTORE_API_PORT}/ready" | grep -q '"status":"ok"'; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  "${compose[@]}" --profile backup-test logs --tail=100 api-restore-test
  printf 'DR drill: restored API did not become ready\n' >&2
  exit 1
fi

curl -fsS "http://127.0.0.1:${RESTORE_API_PORT}/" | grep -q '"service":"fantappero-api"'
printf 'DR drill: PASS (database fingerprints, constraints, avatars and API readiness)\n'
