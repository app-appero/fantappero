#!/bin/sh
# Restore avatars to a new, empty staging directory; never to the live volume.

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
RESTORE_AVATAR_FILE=${RESTORE_AVATAR_FILE:-latest}
RESTORE_AVATAR_TARGET=${RESTORE_AVATAR_TARGET:-/restore/avatars}

if [ "${CONFIRM_AVATAR_RESTORE:-}" != isolated-target-only ]; then
  log error avatar_restore_refused reason=missing_confirmation
  exit 2
fi
case "$RESTORE_AVATAR_TARGET" in
  /restore/*) ;;
  *)
    log error avatar_restore_refused reason=unsafe_target
    exit 2
    ;;
esac

if [ "$RESTORE_AVATAR_FILE" = latest ]; then
  archive=$(find "$BACKUP_ROOT/avatars/daily" -maxdepth 1 -type f -name 'fantappero-*.tar.gz' \
    | sort -r | head -n 1)
else
  case "$RESTORE_AVATAR_FILE" in
    /*) archive="$RESTORE_AVATAR_FILE" ;;
    *) archive="$BACKUP_ROOT/avatars/daily/$RESTORE_AVATAR_FILE" ;;
  esac
fi

case "$archive" in
  "$BACKUP_ROOT"/avatars/daily/*|"$BACKUP_ROOT"/avatars/weekly/*) ;;
  *)
    log error avatar_restore_refused reason=archive_outside_backup_root
    exit 2
    ;;
esac

if [ ! -r "$archive" ] || [ ! -r "$archive.meta" ] || [ ! -r "$archive.sha256" ]; then
  log error avatar_restore_refused reason=archive_manifest_or_checksum_missing
  exit 2
fi

(
  cd "$(dirname "$archive")"
  sha256sum -c "$(basename "$archive").sha256"
)

if tar -tzf "$archive" | awk '
  /^\// { bad=1 }
  /(^|\/)\.\.($|\/)/ { bad=1 }
  END { exit bad }
'; then
  :
else
  log error avatar_restore_refused reason=unsafe_archive_paths
  exit 2
fi

mkdir -p "$RESTORE_AVATAR_TARGET"
if find "$RESTORE_AVATAR_TARGET" -mindepth 1 -maxdepth 1 | grep -q .; then
  log error avatar_restore_refused reason=target_not_empty
  exit 2
fi

tar -xzf "$archive" -C "$RESTORE_AVATAR_TARGET"
file_count=$(find "$RESTORE_AVATAR_TARGET" -type f | wc -l | tr -d ' ')
log info avatar_restore_succeeded "archive=$(basename "$archive")" "file_count=$file_count"
