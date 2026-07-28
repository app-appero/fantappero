# Configuration and secrets (EP01-04)

FantApperò separates **environment-specific values** from code. Secrets never belong in the repository, client bundles, or unstructured logs.

## Responsibilities

| Layer | Who owns secrets | Where values live | Validated by |
| --- | --- | --- | --- |
| **API** (`backend`) | Platform / backend team | Root `.env`, secret manager at deploy time | `config.settings.api.ApiSettings` |
| **Worker** (`backend`) | Platform / backend team | Same as API (shared `.env` in dev) | `config.settings.worker.WorkerSettings` |
| **Web** (`apps/web`) | Frontend team | `apps/web/.env` — **public vars only** | `apps/web/src/config/env.ts` |
| **Mobile** (`apps/mobile`) | Mobile team | `apps/mobile/.env` — **public vars only** | `apps/mobile/src/config/env.ts` |
| **Compose (local)** | Developer machine | `infra/local/.env` (optional override) | Documented in [local_environment.md](../development/local_environment.md) |

**Rule:** Provider keys (`API_FOOTBALL_KEY`, etc.) are **backend-only**. Web and mobile must never read or bundle them.

## Environment profiles

`FANTAPPERO_ENV` controls validation strictness:

| Value | Use | Infra vars (`DATABASE_URL`, `REDIS_URL`, Celery URLs) |
| --- | --- | --- |
| `development` | Local dev, Docker stack | **Required** for API/worker startup |
| `staging` / `production` | Deployed environments | **Required** |
| `test` | Pytest / CI unit tests | Optional (relaxed) |

Startup **fails fast** with a readable message when a required variable is missing or invalid. Error messages are **redacted** before logging or serialization.

## File layout

```
.env.example                 # Host-run API + provider secrets (copy → .env)
config/settings/             # Per-component templates (no real secrets)
infra/local/.env.example     # Docker Compose defaults
apps/web/.env.example        # VITE_* public URLs
apps/mobile/.env.example     # EXPO_PUBLIC_* public URLs
backend/src/config/settings/ # Typed Python schemas + redaction
```

All `.env` files are gitignored. Only `*.env.example` files are committed.

## Variable reference (backend)

| Variable | Required (non-test) | Secret | Description |
| --- | --- | --- | --- |
| `FANTAPPERO_ENV` | No (default `development`) | No | Runtime profile |
| `LOG_LEVEL` | No (default `INFO`) | No | Process log level (JSON logs; see [observability_baseline.md](observability_baseline.md)) |
| `ERROR_TRACKING_ENABLED` | No (default `false`) | No | Feature flag for `ErrorTracker` |
| `ERROR_TRACKING_DSN` | No | **Yes** | Optional vendor DSN — never log |
| `DATABASE_URL` | Yes | Yes (password in DSN) | PostgreSQL connection string |
| `REDIS_URL` | Yes | Sometimes | Redis connection string |
| `CELERY_BROKER_URL` | Yes (worker) | Sometimes | Celery broker; defaults from `REDIS_URL` in dev |
| `CELERY_RESULT_BACKEND` | Yes (worker) | Sometimes | Celery result backend |
| `API_FOOTBALL_KEY` | No (scripts only) | **Yes** | API-Football provider key |
| `APISPORTS_KEY` | No | **Yes** | Alias for `API_FOOTBALL_KEY` |

## Variable reference (clients)

| Variable | Required | Secret | Description |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` | Yes (when using API) | No | Web API origin |
| `EXPO_PUBLIC_API_BASE_URL` | Yes (when using API) | No | Mobile API origin |

Client variables are embedded in the bundle — use only non-sensitive URLs.

## Secret redaction

The backend module `config.settings.redaction` masks:

- Passwords in DSNs and URLs (`postgresql://user:***@host`)
- Bearer tokens and `Authorization` headers
- Key/value assignments (`API_FOOTBALL_KEY=…`, `password=…`)

Use `redact_secrets()` / `redact_value()` before logging configuration errors or debugging payloads.

## Rotation (vendor-neutral)

These practices apply regardless of cloud provider:

1. **Store** production secrets in a dedicated secret manager or encrypted env injection — not in git, not in images.
2. **Rotate** provider API keys on a schedule and after any suspected leak; update the manager, then redeploy API/worker.
3. **Scope** keys to least privilege (read-only polling keys where possible).
4. **Audit** access to secret stores; restrict who can read production DSNs.
5. **Local dev** uses committed `.env.example` placeholders (`fantappero_local_dev_only`) — never reuse those passwords outside localhost.

No specific AWS/GCP/Azure product is required at this stage; wire the same variable names into whichever manager you adopt later.

## Verification

Automated checks live in `backend/tests/unit/config/`:

- Valid minimal configuration (test profile)
- Missing / malformed variables
- Redaction of tokens, passwords, DSNs
- Repository scan for accidental secrets in tracked files

Run locally:

```bash
cd backend && python -m pytest tests/unit/config -q
pnpm --filter @fantappero/web test
pnpm --filter @fantappero/mobile test
```

## Related docs

- [Observability baseline](observability_baseline.md) — correlation IDs, JSON logs, metrics, probes
- [Local environment](../development/local_environment.md) — Docker Compose and `.env` precedence
- [ADR-0003](../adr/ADR-0003-monorepo.md) — monorepo boundaries and secret placement
- [Quality gates](../development/quality_gates.md) — CI runs config tests automatically
