#!/bin/sh
# Minimal interval scheduler for the dedicated backup container.

set -u

interval=${BACKUP_INTERVAL_SECONDS:-86400}
case "$interval" in
  ''|*[!0-9]*|0)
    printf 'timestamp=%s level=error event=invalid_configuration field=BACKUP_INTERVAL_SECONDS\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    exit 2
    ;;
esac

if [ "$interval" -lt 300 ]; then
  printf 'timestamp=%s level=error event=invalid_configuration field=BACKUP_INTERVAL_SECONDS minimum=300\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit 2
fi

terminate=false
trap 'terminate=true' HUP INT TERM

while [ "$terminate" = false ]; do
  cycle_started=$(date -u +%s)
  /scripts/backup_postgres.sh || true
  [ "$terminate" = false ] || break
  cycle_finished=$(date -u +%s)
  cycle_duration=$((cycle_finished - cycle_started))
  sleep_seconds=$((interval - cycle_duration))
  if [ "$sleep_seconds" -lt 1 ]; then
    sleep_seconds=1
  fi
  printf 'timestamp=%s level=info event=backup_scheduler_sleep seconds=%s cycle_duration_seconds=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sleep_seconds" "$cycle_duration"
  sleep "$sleep_seconds" &
  wait $! || true
done

printf 'timestamp=%s level=info event=backup_scheduler_stopped\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
