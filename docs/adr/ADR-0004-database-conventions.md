# ADR-0004 — Database conventions and migration baseline

| Field | Value |
| --- | --- |
| Status | Accepted (EP01-06 baseline) |
| Date | 2026-07-28 |
| Card | EP01-06 |
| Relations | ADR-0001 (application source of truth); ADR-0003 (monorepo layout); EP01-02 (local Postgres); EP01-03 (migration gate) |

## Context

FantApperò stores application state in PostgreSQL. EP01-02 delivers a local Postgres 16 stack; EP01-04 wires `DATABASE_URL` into typed settings. Until EP01-06 there was no ORM layer, no schema baseline, and no drift detection — only raw `psycopg` health probes.

Product domains (fixtures, squads, markets, scoring) are not implemented yet. This ADR establishes **conventions and infrastructural baseline only**, avoiding premature tables for entities still under design.

## Decision

### 1. Ownership and layout

| Artifact | Location |
| --- | --- |
| ORM base, mixins, session helpers | `backend/src/database/` |
| Alembic config | `backend/alembic.ini`, `backend/alembic/` |
| Revisions | `backend/alembic/versions/` (single linear head) |
| Integration tests | `backend/tests/integration/database/` |
| Drift check | `infra/scripts/check_schema_drift.py` (`alembic check`) |

Domain normalization (`backend/src/sports_data/`) stays separate from ORM models. Map at repository boundaries per ADR-0001.

### 2. Naming conventions

- **Tables**: plural `snake_case` (`system_flags`, future `match_events`).
- **Columns**: `snake_case`.
- **Constraints/indexes**: SQLAlchemy `MetaData(naming_convention=…)` — `pk_`, `fk_`, `uq_`, `ix_`, `ck_` prefixes (see `database/base.py`).
- **PostgreSQL enums**: `snake_case` type names matching the Python enum (`flag_scope`).

### 3. Primary keys

- Domain and infrastructural rows use **UUID v4** stored as PostgreSQL `uuid`.
- Default generation: `gen_random_uuid()` via the **pgcrypto** extension (created in baseline migration).
- Provider-native integer IDs remain separate columns inside the anti-corruption layer, not as primary keys (ADR-0001).

### 4. Timestamps (UTC)

- All persisted datetimes use PostgreSQL **`timestamptz`** (`DateTime(timezone=True)`).
- Standard audit columns: `created_at`, `updated_at`.
- Server default: `timezone('utc', now())`.
- Application code uses timezone-aware UTC (`datetime.now(UTC)`); the `UTCDateTime` type normalizes naive values on bind.
- **Never** store local wall-clock time without offset.

### 5. Enumerations

- Python `enum.Enum` / `StrEnum` mirrored as native PostgreSQL `ENUM` types.
- Enum type names and member values are `snake_case` strings.
- Prefer native enums over unchecked `VARCHAR` for closed sets (status, scope, role).

### 6. Soft delete

- Provided via optional `SoftDeleteMixin` (`deleted_at timestamptz NULL`).
- Apply **only when product semantics require retained history** (e.g. user-facing entities with audit/legal constraints).
- Baseline infrastructural tables (`system_flags`) do **not** use soft delete.
- Hard delete remains the default for idempotent infra rows and ephemeral job state.

### 7. Baseline schema (EP01-06)

The initial revision `7f3a1c9e2b04` creates:

| Object | Purpose |
| --- | --- |
| Extension `pgcrypto` | UUID generation |
| Enum `flag_scope` | Demonstrates enum convention |
| Table `system_flags` | Infrastructural key/value flags (UUID PK, UTC timestamps, unique `key`, index on `scope`) |

No product-domain tables (fixtures, players, leagues, markets) in this card.

### 8. Migrations workflow

```bash
# Apply latest schema (from monorepo root)
make migrate

# Controlled rollback to empty (local/dev only)
make migrate-down

# Detect model ↔ DB drift
make migrate-check
```

Commands run from `backend/` using `DATABASE_URL`. Alembic reads the URL from typed settings / environment (`database/session.py`).

**Autogenerate policy**

1. Change SQLAlchemy models under `database/models/`.
2. `cd backend && python -m alembic revision --autogenerate -m "describe change"`.
3. Review generated SQL manually — autogenerate is never blind-commit.
4. `make migrate-check` must pass before merge.

### 9. Transactions

- One logical unit of work = one SQLAlchemy `Session` transaction.
- Use `session_scope()` (`database/session.py`) in scripts/tasks: commit on success, rollback on exception.
- API request handlers and Celery tasks should keep transactions **short**; do not hold DB connections across external HTTP calls.
- Migrations run inside Alembic's transaction per revision (`upgrade()` / `downgrade()`).

### 10. Indexes

- Primary keys and unique constraints are indexed by Postgres automatically.
- Add secondary indexes for **proven** lookup paths; avoid speculative indexes on tables that do not exist yet.
- Baseline: `ix_system_flags_scope` for scoped flag queries.
- Name all indexes via naming convention (`ix_<columns>`).

### 11. Rollback strategy

| Scenario | Action |
| --- | --- |
| Local/dev failed migration | `alembic downgrade -1` or `make migrate-down` to `base` |
| Production bad migration | Forward-fix with a **new** revision; avoid rewriting published history |
| Destructive downgrade | Only in non-production; document data loss in revision docstring |
| Extension drop (`pgcrypto`) | Baseline downgrade drops extension — safe only on empty/dev DB |

**Rule**: never edit a revision already applied in shared environments; add a corrective forward migration instead.

### 12. CI gate

EP01-06 promotes the `migrations` CI job from informative to **required**:

- Layout + single Alembic head (`infra/scripts/check_migrations.py`)
- `alembic upgrade head` + `alembic check` against ephemeral Postgres
- Integration tests under `tests/integration/database/`

Unit tests (`python-test` job) skip DB tests when `DATABASE_URL` is unset.

## Consequences

### Positive

- Reproducible schema from empty Postgres with verified downgrade path.
- Drift detection catches model/migration skew before merge.
- Conventions documented before product tables land.

### Negative / costs

- Native PostgreSQL enums require explicit migration steps to rename/extend values.
- Integration tests need Postgres (Compose locally, service container in CI).
- Two layers (SPD normalization + ORM) require mapping discipline.

### Non-decisions (deferred)

- Async SQLAlchemy (`asyncpg`) — sync `psycopg` sufficient for MVP scaffold.
- Row-level security, partitioning, read replicas.
- Product entity schemas (M1+ cards).

## Alternatives considered

| Alternative | Why rejected |
| --- | --- |
| Integer serial PKs | Conflicts with distributed IDs and ADR-0001 provider boundary |
| `TIMESTAMP WITHOUT TIME ZONE` | Ambiguous timezone semantics |
| Single `backend/migrations/` folder without Alembic | Fails EP01-03 coherence checker |
| Full domain schema now | Crystallizes unimplemented entities; violates card scope |
