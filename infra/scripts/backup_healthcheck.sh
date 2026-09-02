#!/bin/sh
# Fail when no successful backup exists or the most recent one is too old.

set -eu

state_file=${BACKUP_ROOT:-/backups}/state/last_success.env
failure_file=${BACKUP_ROOT:-/backups}/state/last_failure.env
max_age=${BACKUP_MAX_AGE_SECONDS:-93600}

case "$max_age" in
  ''|*[!0-9]*|0) exit 2 ;;
esac

[ -r "$state_file" ] || exit 1
last_success=$(sed -n 's/^last_success_epoch=//p' "$state_file")
case "$last_success" in
  ''|*[!0-9]*) exit 1 ;;
esac

now=$(date -u +%s)
age=$((now - last_success))
[ "$age" -ge 0 ] || exit 1
[ "$age" -le "$max_age" ] || exit 1

if [ -r "$failure_file" ]; then
  last_failure=$(sed -n 's/^last_failure_epoch=//p' "$failure_file")
  case "$last_failure" in
    ''|*[!0-9]*) exit 1 ;;
  esac
  [ "$last_failure" -le "$last_success" ] || exit 1
fi
