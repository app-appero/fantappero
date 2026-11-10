#!/bin/sh
# Reconcile pnpm node_modules after bind-mounting host source (Windows junctions break in Linux).
set -e
cd /app

if [ ! -e apps/web/node_modules/@fantappero/ui ] || [ ! -e apps/web/node_modules/@fantappero/api-client ] || [ ! -e apps/web/node_modules/react ] || [ ! -e packages/ui/node_modules/@fantappero/contracts ] || [ ! -e packages/api-client/node_modules/@fantappero/contracts ]; then
  echo "Installing web workspace dependencies in container..."
  CI=true pnpm install --prefer-offline
fi

# Railway imposta sempre le proprie variabili RAILWAY_* su ogni servizio; lo
# stack locale (docker-compose) no. Su Railway si serve sempre la build già
# pronta (pnpm --filter @fantappero/web start, vedi Dockerfile.web), a
# prescindere dal CMD/Custom Start Command impostato nel pannello — niente da
# configurare a mano lì. In locale resta il CMD di default (dev server live).
if [ -n "$RAILWAY_ENVIRONMENT_NAME" ]; then
  exec pnpm --filter @fantappero/web start
fi

exec "$@"
