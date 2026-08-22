#!/bin/sh
# Reconcile pnpm node_modules after bind-mounting host source (Windows junctions break in Linux).
set -e
cd /app

if [ ! -e apps/web/node_modules/@fantappero/ui ] || [ ! -e apps/web/node_modules/@fantappero/api-client ] || [ ! -e apps/web/node_modules/react ]; then
  echo "Installing web workspace dependencies in container..."
  CI=true pnpm install --prefer-offline
fi

exec "$@"
