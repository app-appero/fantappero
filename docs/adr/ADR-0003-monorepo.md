# ADR-0003 — Monorepo layout and domain boundaries

| Field | Value |
| --- | --- |
| Status | Accepted (EP01-01 baseline) |
| Date | 2026-07-27 |
| Card | EP01-01 |
| Relations | Architettura tecnica MVP §14.4; ADR-0001 (provider boundary); EP00 work under `backend/` |

## Context

FantApperò is an API-first modular monolith (FastAPI + React + React Native/Expo + PostgreSQL + Redis/workers). EP00 already landed sports-data fixtures, normalization, and tooling under `backend/`, while architecture §14.4 suggested `services/api` and the EP01-01 card listed `apps/api/` as an indicative path.

Without an explicit layout decision, clients, shared packages, and the SPD adapter risk circular imports and unclear ownership of secrets.

## Decision

1. **Keep the API at `backend/`** (not `apps/api/` or `services/api/`). This preserves EP00 paths (`backend/src/sports_data`, fixtures, scripts) and matches the repository README already used by M0 work. Documented deviation from the indicative card path and from architecture §14.4 naming.
2. **Clients live under `apps/`**: `apps/web` (React + Vite), `apps/mobile` (Expo). They consume only `@fantappero/contracts` and `@fantappero/ui` plus the HTTP API. They never import Python modules or hold provider secrets.
3. **Shared TypeScript packages live under `packages/`**:
   - `packages/contracts` — shared types / future OpenAPI clients (no business rules).
   - `packages/ui` — design tokens / presentational primitives (no league/scoring/market logic).
4. **Dependency direction (acyclic)**:
   - `apps/*` → `packages/*` → (nothing from apps)
   - `packages/ui` must not depend on `packages/contracts` for this scaffold (tokens only); both may later depend on a narrower shared package if needed.
   - `backend` does not depend on JS packages; OpenAPI remains the contract source of truth for later generation into `packages/contracts`.
   - Sport provider access stays inside `backend` (ADR-0001).
5. **Tooling**:
   - JavaScript: **pnpm workspaces** with a single root lockfile (`pnpm-lock.yaml`).
   - Python: `backend/pyproject.toml` with pinned runtime/dev dependencies.
   - Uniform commands via root `Makefile` and root `package.json` scripts (Windows-friendly `pnpm`/`python` equivalents documented in README).
6. **Bootstrap requires no cloud services or secrets.** Health surfaces (`/health`, web page, mobile screen) work offline after local install.

## Consequences

### Positive

- EP00 artifacts keep working without a move/rename.
- Clear one-way dependency graph reduces circular coupling risk.
- Reproducible setup from a clean clone with locked versions.

### Negative / costs

- Naming differs from architecture §14.4 (`services/api`) and from the card’s `apps/api/` hint — newcomers must read this ADR.
- Two package ecosystems (Python + pnpm) instead of a single toolchain.

### Non-decisions (out of scope for EP01-01)

- Docker Compose / local Postgres/Redis — delivered in EP01-02 (`compose.yaml`, `infra/local/`, `docs/development/local_environment.md`).
- CI quality gates — delivered in EP01-03 (`.github/workflows/ci.yml`, `docs/development/quality_gates.md`).
- Secret management beyond `.env.example` hygiene — delivered in EP01-04 (`config/settings/`, `docs/operations/configuration_and_secrets.md`).
- Alembic / schema baseline — delivered in EP01-06 (`backend/alembic/`, ADR-0004).
- Product features for M1–M5.

## Alternatives considered

| Alternative | Why rejected |
| --- | --- |
| Move API to `apps/api/` or `services/api/` now | Breaks EP00 paths and scripts for no functional gain in M0 |
| npm/yarn workspaces | pnpm already available; stricter linking fits monorepo boundaries |
| Implement product domains in this card | Out of scope; scaffold only |
