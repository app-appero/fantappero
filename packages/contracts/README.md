# packages/contracts

Shared contract types for web and mobile (OpenAPI client generation comes later).

## Boundaries

- No fantasy business logic.
- No secrets or sports-provider calls.
- Versions stay aligned with the `backend` HTTP API (`/api/v1` later).

## Commands

```bash
pnpm --filter @fantappero/contracts build
pnpm --filter @fantappero/contracts test
```

## Status

EP01-01 scaffold — health/service type stubs only.
