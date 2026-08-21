#!/bin/sh
# Restore a dump only to an explicitly isolated PostgreSQL test database.

set -eu

log() {
  level="$1"
  event="$2"
  shift 2
  printf 'timestamp=%s level=%s event=%s' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$level" "$event"
  for field in "$@"; do
    printf ' %s' "$field"
  done
  printf '\n'
}

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
RESTORE_BACKUP_FILE=${RESTORE_BACKUP_FILE:-latest}
RESTORE_TARGET_HOST=${RESTORE_TARGET_HOST:-postgres-test}
RESTORE_TARGET_PORT=${RESTORE_TARGET_PORT:-5432}
RESTORE_TARGET_DATABASE=${RESTORE_TARGET_DATABASE:-fantappero_restore_ep12}

: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
export PGPASSWORD

if [ "${CONFIRM_RESTORE:-}" != isolated-test-only ]; then
  log error restore_refused reason=missing_confirmation
  exit 2
fi
if [ "$RESTORE_TARGET_HOST" != postgres-test ]; then
  log error restore_refused reason=host_not_allowlisted
  exit 2
fi
case "$RESTORE_TARGET_DATABASE" in
  fantappero_restore_[a-z0-9_]*) ;;
  *)
    log error restore_refused reason=unsafe_database_name
    exit 2
    ;;
esac

if [ "$RESTORE_BACKUP_FILE" = latest ]; then
  archive=$(find "$BACKUP_ROOT/postgres/daily" -maxdepth 1 -type f -name 'fantappero-*.dump' \
    | sort -r | head -n 1)
else
  case "$RESTORE_BACKUP_FILE" in
    /*) archive="$RESTORE_BACKUP_FILE" ;;
    *) archive="$BACKUP_ROOT/postgres/daily/$RESTORE_BACKUP_FILE" ;;
  esac
fi

case "$archive" in
  "$BACKUP_ROOT"/postgres/daily/*|"$BACKUP_ROOT"/postgres/weekly/*) ;;
  *)
    log error restore_refused reason=archive_outside_backup_root
    exit 2
    ;;
esac

if [ ! -r "$archive" ] || [ ! -r "$archive.meta" ] || [ ! -r "$archive.sha256" ]; then
  log error restore_refused reason=archive_manifest_or_checksum_missing
  exit 2
fi

(
  cd "$(dirname "$archive")"
  sha256sum -c "$(basename "$archive").sha256"
)
pg_restore --list "$archive" >/dev/null

started_epoch=$(date -u +%s)
log info restore_started "archive=$(basename "$archive")" \
  "target_host=$RESTORE_TARGET_HOST" "target_database=$RESTORE_TARGET_DATABASE"

dropdb --if-exists --force \
  --host="$RESTORE_TARGET_HOST" --port="$RESTORE_TARGET_PORT" --username="$PGUSER" \
  "$RESTORE_TARGET_DATABASE"
createdb \
  --host="$RESTORE_TARGET_HOST" --port="$RESTORE_TARGET_PORT" --username="$PGUSER" \
  "$RESTORE_TARGET_DATABASE"

if ! pg_restore \
    --exit-on-error \
    --single-transaction \
    --no-owner \
    --no-privileges \
    --host="$RESTORE_TARGET_HOST" \
    --port="$RESTORE_TARGET_PORT" \
    --username="$PGUSER" \
    --dbname="$RESTORE_TARGET_DATABASE" \
    "$archive"; then
  log error restore_failed target_database="$RESTORE_TARGET_DATABASE"
  exit 1
fi

invalid_constraints=$(psql \
  --host="$RESTORE_TARGET_HOST" --port="$RESTORE_TARGET_PORT" --username="$PGUSER" \
  --dbname="$RESTORE_TARGET_DATABASE" --no-align --tuples-only --set=ON_ERROR_STOP=1 \
  --command="SELECT count(*) FROM pg_constraint WHERE connamespace = 'public'::regnamespace AND NOT convalidated;")
migration_rows=$(psql \
  --host="$RESTORE_TARGET_HOST" --port="$RESTORE_TARGET_PORT" --username="$PGUSER" \
  --dbname="$RESTORE_TARGET_DATABASE" --no-align --tuples-only --set=ON_ERROR_STOP=1 \
  --command='SELECT count(*) FROM alembic_version;')

meta_value() {
  key="$1"
  sed -n "s/^$key=//p" "$archive.meta"
}

restored_scalar() {
  psql --host="$RESTORE_TARGET_HOST" --port="$RESTORE_TARGET_PORT" --username="$PGUSER" \
    --dbname="$RESTORE_TARGET_DATABASE" --no-align --tuples-only --set=ON_ERROR_STOP=1 \
    --command="$1"
}

expected_revision=$(meta_value schema_revision)
actual_revision=$(restored_scalar 'SELECT version_num FROM alembic_version;')

if [ "$invalid_constraints" != 0 ] || [ "$migration_rows" != 1 ] \
  || [ -z "$expected_revision" ] || [ "$actual_revision" != "$expected_revision" ]; then
  log error restore_integrity_failed "invalid_constraints=$invalid_constraints" \
    "migration_rows=$migration_rows" "expected_revision=$expected_revision" \
    "actual_revision=$actual_revision"
  exit 1
fi

finished_epoch=$(date -u +%s)
log info restore_succeeded "duration_seconds=$((finished_epoch - started_epoch))" \
  "invalid_constraints=$invalid_constraints" "migration_rows=$migration_rows" \
  "schema_revision=matched" "target_database=$RESTORE_TARGET_DATABASE"
