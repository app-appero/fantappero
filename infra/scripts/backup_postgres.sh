#!/bin/sh
# Create an atomic PostgreSQL custom-format dump and an avatar archive.
# Intended to run inside the postgres-backup Compose service.

set -eu

umask 077

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

require_positive_integer() {
  name="$1"
  value="$2"
  case "$value" in
    ''|*[!0-9]*|0)
      log error invalid_configuration "field=$name"
      exit 2
      ;;
  esac
}

notify_failure() {
  reason="$1"
  webhook_url="${BACKUP_ALERT_WEBHOOK_URL:-}"
  if [ -z "$webhook_url" ]; then
    return 0
  fi
  payload=$(printf '{"service":"fantappero-postgres-backup","status":"failed","reason":"%s"}' "$reason")
  if wget -q -T 10 -O /dev/null \
    --header='Content-Type: application/json' \
    --post-data="$payload" "$webhook_url"; then
    log info backup_alert_sent
  else
    log error backup_alert_failed
  fi
}

write_failure_state() {
  reason="$1"
  now_epoch=$(date -u +%s)
  {
    printf 'last_failure_epoch=%s\n' "$now_epoch"
    printf 'last_failure_reason=%s\n' "$reason"
  } > "$STATE_DIR/last_failure.env.tmp"
  mv "$STATE_DIR/last_failure.env.tmp" "$STATE_DIR/last_failure.env"
  notify_failure "$reason"
}

prune_archive_set() {
  directory="$1"
  suffix="$2"
  keep="$3"
  find "$directory" -maxdepth 1 -type f -name "fantappero-*.$suffix" \
    | sort -r \
    | awk -v keep="$keep" 'NR > keep' \
    | while IFS= read -r obsolete; do
        [ -n "$obsolete" ] || continue
        rm -f -- "$obsolete" "$obsolete.sha256" "$obsolete.meta"
        log info backup_retention_pruned "file=$(basename "$obsolete")"
      done
}

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
AVATAR_SOURCE=${AVATAR_SOURCE:-/avatars}
DAILY_RETENTION=${BACKUP_DAILY_RETENTION_COUNT:-14}
WEEKLY_RETENTION=${BACKUP_WEEKLY_RETENTION_COUNT:-8}
MAX_ATTEMPTS=${BACKUP_MAX_ATTEMPTS:-3}
RETRY_DELAY_SECONDS=${BACKUP_RETRY_DELAY_SECONDS:-30}
WEEKLY_DAY_UTC=${BACKUP_WEEKLY_DAY_UTC:-7}

case "$BACKUP_ROOT" in
  /backups|/backups/*) ;;
  *)
    log error unsafe_backup_root
    exit 2
    ;;
esac

require_positive_integer BACKUP_DAILY_RETENTION_COUNT "$DAILY_RETENTION"
require_positive_integer BACKUP_WEEKLY_RETENTION_COUNT "$WEEKLY_RETENTION"
require_positive_integer BACKUP_MAX_ATTEMPTS "$MAX_ATTEMPTS"
require_positive_integer BACKUP_RETRY_DELAY_SECONDS "$RETRY_DELAY_SECONDS"
case "$WEEKLY_DAY_UTC" in
  1|2|3|4|5|6|7) ;;
  *)
    log error invalid_configuration field=BACKUP_WEEKLY_DAY_UTC
    exit 2
    ;;
esac

: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

PGPORT=${PGPORT:-5432}
PGCONNECT_TIMEOUT=${PGCONNECT_TIMEOUT:-10}
export PGPORT PGCONNECT_TIMEOUT PGPASSWORD

POSTGRES_DAILY="$BACKUP_ROOT/postgres/daily"
POSTGRES_WEEKLY="$BACKUP_ROOT/postgres/weekly"
AVATAR_DAILY="$BACKUP_ROOT/avatars/daily"
AVATAR_WEEKLY="$BACKUP_ROOT/avatars/weekly"
STATE_DIR="$BACKUP_ROOT/state"
mkdir -p "$POSTGRES_DAILY" "$POSTGRES_WEEKLY" "$AVATAR_DAILY" "$AVATAR_WEEKLY" "$STATE_DIR"

# The lock lives on the shared backup mount, not in the container-local /tmp:
# scheduled and one-shot Compose containers must exclude each other too.
LOCK_FILE="$STATE_DIR/backup.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log warning backup_already_running
  exit 75
fi

dump_partial=''
avatar_partial=''
cleanup() {
  [ -z "$dump_partial" ] || rm -f -- "$dump_partial"
  [ -z "$avatar_partial" ] || rm -f -- "$avatar_partial"
}
trap cleanup EXIT HUP INT TERM

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
dump_name="fantappero-$timestamp.dump"
avatar_name="fantappero-$timestamp.tar.gz"
dump_final="$POSTGRES_DAILY/$dump_name"
avatar_final="$AVATAR_DAILY/$avatar_name"
dump_partial="$dump_final.partial"
avatar_partial="$avatar_final.partial"
started_epoch=$(date -u +%s)

attempt=1
success=false
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  rm -f -- "$dump_partial" "$avatar_partial"
  log info backup_attempt_started "attempt=$attempt" "max_attempts=$MAX_ATTEMPTS" \
    "database=$PGDATABASE"

  if pg_dump \
      --format=custom \
      --compress=6 \
      --no-owner \
      --no-privileges \
      --file="$dump_partial" \
      --host="$PGHOST" \
      --port="$PGPORT" \
      --username="$PGUSER" \
      "$PGDATABASE" \
    && pg_restore --list "$dump_partial" >/dev/null \
    && tar -czf "$avatar_partial" -C "$AVATAR_SOURCE" . \
    && tar -tzf "$avatar_partial" >/dev/null; then
    success=true
    break
  fi

  log warning backup_attempt_failed "attempt=$attempt" "max_attempts=$MAX_ATTEMPTS"
  if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
    sleep "$RETRY_DELAY_SECONDS"
  fi
  attempt=$((attempt + 1))
done

if [ "$success" != true ]; then
  write_failure_state attempts_exhausted
  log error backup_failed "attempts=$MAX_ATTEMPTS"
  exit 1
fi

psql_scalar() {
  psql --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" --dbname="$PGDATABASE" \
    --no-align --tuples-only --set=ON_ERROR_STOP=1 --command="$1"
}

# Record the expected migration revision. Row counts are intentionally not
# captured here: a separate query would not share pg_dump's MVCC snapshot on a
# live system and could produce a false mismatch during normal writes.
if ! schema_revision=$(psql_scalar 'SELECT version_num FROM alembic_version;'); then
  write_failure_state schema_manifest_failed
  log error backup_failed reason=schema_manifest_failed
  exit 1
fi

mv "$dump_partial" "$dump_final"
dump_partial=''
mv "$avatar_partial" "$avatar_final"
avatar_partial=''

dump_size=$(wc -c < "$dump_final" | tr -d ' ')
avatar_size=$(wc -c < "$avatar_final" | tr -d ' ')
finished_epoch=$(date -u +%s)
duration_seconds=$((finished_epoch - started_epoch))
dump_sha256=$(sha256sum "$dump_final" | cut -d ' ' -f 1)
avatar_sha256=$(sha256sum "$avatar_final" | cut -d ' ' -f 1)

{
  printf 'created_at_utc=%s\n' "$timestamp"
  printf 'database=%s\n' "$PGDATABASE"
  printf 'format=postgresql-custom\n'
  printf 'size_bytes=%s\n' "$dump_size"
  printf 'sha256=%s\n' "$dump_sha256"
  printf 'schema_revision=%s\n' "$schema_revision"
} > "$dump_final.meta"
{
  printf 'created_at_utc=%s\n' "$timestamp"
  printf 'source=avatar-volume\n'
  printf 'format=tar-gzip\n'
  printf 'size_bytes=%s\n' "$avatar_size"
  printf 'sha256=%s\n' "$avatar_sha256"
} > "$avatar_final.meta"

# Each checksum file covers both the payload and its schema/metadata manifest.
(
  cd "$POSTGRES_DAILY"
  sha256sum "$dump_name" "$dump_name.meta" > "$dump_name.sha256"
)
(
  cd "$AVATAR_DAILY"
  sha256sum "$avatar_name" "$avatar_name.meta" > "$avatar_name.sha256"
)

if [ "$(date -u +%u)" = "$WEEKLY_DAY_UTC" ]; then
  weekly_date=${timestamp%%T*}
  existing_weekly_dump=$(find "$POSTGRES_WEEKLY" -maxdepth 1 -type f \
    -name "fantappero-${weekly_date}T*.dump" -print -quit)
  existing_weekly_avatar=$(find "$AVATAR_WEEKLY" -maxdepth 1 -type f \
    -name "fantappero-${weekly_date}T*.tar.gz" -print -quit)
  if [ -n "$existing_weekly_dump" ] && [ -n "$existing_weekly_avatar" ]; then
    log info weekly_backup_already_present "date=$weekly_date"
  else
    cp "$dump_final" "$dump_final.sha256" "$dump_final.meta" "$POSTGRES_WEEKLY/"
    cp "$avatar_final" "$avatar_final.sha256" "$avatar_final.meta" "$AVATAR_WEEKLY/"
    log info weekly_backup_promoted "postgres_file=$dump_name" "avatar_file=$avatar_name"
  fi
fi

prune_archive_set "$POSTGRES_DAILY" dump "$DAILY_RETENTION"
prune_archive_set "$POSTGRES_WEEKLY" dump "$WEEKLY_RETENTION"
prune_archive_set "$AVATAR_DAILY" tar.gz "$DAILY_RETENTION"
prune_archive_set "$AVATAR_WEEKLY" tar.gz "$WEEKLY_RETENTION"

{
  printf 'last_success_epoch=%s\n' "$finished_epoch"
  printf 'last_success_utc=%s\n' "$timestamp"
  printf 'postgres_file=%s\n' "$dump_name"
  printf 'avatar_file=%s\n' "$avatar_name"
  printf 'duration_seconds=%s\n' "$duration_seconds"
  printf 'postgres_size_bytes=%s\n' "$dump_size"
  printf 'avatar_size_bytes=%s\n' "$avatar_size"
} > "$STATE_DIR/last_success.env.tmp"
mv "$STATE_DIR/last_success.env.tmp" "$STATE_DIR/last_success.env"
rm -f "$STATE_DIR/last_failure.env"

{
  printf '# TYPE fantappero_backup_last_success_timestamp_seconds gauge\n'
  printf 'fantappero_backup_last_success_timestamp_seconds %s\n' "$finished_epoch"
  printf '# TYPE fantappero_backup_duration_seconds gauge\n'
  printf 'fantappero_backup_duration_seconds %s\n' "$duration_seconds"
  printf '# TYPE fantappero_backup_postgres_size_bytes gauge\n'
  printf 'fantappero_backup_postgres_size_bytes %s\n' "$dump_size"
  printf '# TYPE fantappero_backup_avatar_size_bytes gauge\n'
  printf 'fantappero_backup_avatar_size_bytes %s\n' "$avatar_size"
} > "$STATE_DIR/backup.prom.tmp"
mv "$STATE_DIR/backup.prom.tmp" "$STATE_DIR/backup.prom"

log info backup_succeeded "attempt=$attempt" "duration_seconds=$duration_seconds" \
  "postgres_file=$dump_name" "postgres_size_bytes=$dump_size" \
  "avatar_file=$avatar_name" "avatar_size_bytes=$avatar_size"
