# Environment templates per runtime (EP01-04)
#
# Copy the relevant fragment into a gitignored `.env` file:
#   - API / worker / scripts → repo root `.env` (see ../../.env.example)
#   - Compose stack           → infra/local/.env (see ../../infra/local/.env.example)
#   - Web client              → apps/web/.env
#   - Mobile client           → apps/mobile/.env
#
# Schemas (typed validation):
#   - API / worker: backend/src/config/settings/
#   - Web:          apps/web/src/config/env.ts
#   - Mobile:       apps/mobile/src/config/env.ts
#
# Full guide: docs/operations/configuration_and_secrets.md
