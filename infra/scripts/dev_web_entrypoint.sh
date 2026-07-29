#!/bin/sh
# Install Linux workspace deps, then start Vite (bind-mounted monorepo).
set -e

cd /app

echo "Syncing JS dependencies for Linux container..."
pnpm install --frozen-lockfile

exec pnpm dev:web
