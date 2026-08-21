# Quality gates (EP01-03)

Pipeline CI su GitHub Actions e comandi locali equivalenti. Obiettivo: bloccare
regressioni, build non valide e migrazioni incoerenti **prima del merge**, senza
segreti di produzione.

Workflow: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)

## Job obbligatori vs informativi

| Job CI | Ruolo | Comando locale |
| --- | --- | --- |
| `python-lint` | **Obbligatorio** — Ruff lint + format check | `make lint` + `make format` |
| `python-test` | **Obbligatorio** — pytest backend | `make test-api` |
| `js-lint` | **Obbligatorio** — `tsc` via `pnpm lint` | `pnpm lint` |
| `js-typecheck` | **Obbligatorio** — `pnpm typecheck` | `make typecheck` |
| `js-test` | **Obbligatorio** — test workspace JS | `make test-js` |
| `js-build` | **Obbligatorio** — packages + web + mobile | `make build` |
| `ci-success` | **Obbligatorio** — aggregato (branch protection) | `make quality` |
| `migrations` | **Obbligatorio** — Alembic upgrade, drift check, integration DB tests | `make migrate && make migrate-check` (richiede `DATABASE_URL`) |
| `ep00-extra-tests` | **Informativo** — suite tools/experiments | vedi sotto |
| `performance-smoke` | **Informativo** — stack isolato + seed + Celery + k6 smoke EP12-03 | `PERF_USER_COUNT=1 make performance-smoke` |

In branch protection su GitHub, richiedere il check **`CI success`** (job `ci-success`).
I job informativi non devono essere required.

## Riproduzione locale (parità CI)

Prerequisiti: Python ≥ 3.12, Node ≥ 20, pnpm 9 (`corepack enable` o install globale).

```bash
# Setup una tantum
make setup
# oppure:
#   pnpm install
#   python -m pip install -e "./backend[dev]"

# Tutti i gate obbligatori + check migrazioni
make quality
```

Gate singoli:

```bash
make lint              # ruff check src tests + pnpm lint
make format            # ruff format --check src tests
make typecheck         # pnpm typecheck
make test              # pytest backend + pnpm test
make build             # packages + web + mobile
make check-migrations  # layout + single head; drift se DATABASE_URL è impostato
make migrate           # alembic upgrade head (Postgres locale)
make migrate-check     # alembic check — rileva drift schema
```

Equivalenti senza Make (PowerShell / cmd):

```bash
cd backend && python -m ruff check src tests
cd backend && python -m ruff format --check src tests
pnpm lint
pnpm typecheck
cd backend && python -m pytest
pnpm test
pnpm run build:packages && pnpm run build:web && pnpm --filter @fantappero/mobile build
python infra/scripts/check_migrations.py
```

Per riformattare in-place (non è un gate CI; prepara il format check):

```bash
cd backend && python -m ruff format src tests
```

### Suite informative EP00 (non in `make quality`)

```bash
python -m pip install "pytest==8.4.1"
(cd tools/api_quota_estimator && python -m pytest)
(cd experiments/rating_beta && python -m pytest)
```

### Smoke performance EP12-03 (non in `make quality`)

```bash
PERF_USER_COUNT=1 make performance-smoke
```

Il job gira solo su invocazione manuale o branch M5. È informativo perché la capacità
del runner GitHub non rappresenta il pilot; il full gate resta `make performance-test`
su un host controllato, secondo il runbook `docs/operations/performance_capacity.md`.

## Cache e concorrenza

- **Concurrency**: un solo run attivo per `workflow + ref`; i run precedenti sulla
  stessa PR/branch vengono cancellati (`cancel-in-progress`).
- **Cache pip**: chiave da `backend/pyproject.toml` (e dai
  `pyproject.toml` EP00 nel job informativo).
- **Cache pnpm**: chiave da `pnpm-lock.yaml` — un cambio al lockfile invalida la
  cache Node/pnpm al run successivo.
- Install JS in CI: `pnpm install --frozen-lockfile` (fallisce se lockfile e
  manifest divergono).

## Segreti

I job **non** richiedono secret GitHub né chiavi provider (`API_FOOTBALL_KEY`,
DB di produzione, ecc.). I test unitari backend e JS girano offline; il check
migrazioni attuale è solo struttuale (nessun `DATABASE_URL` obbligatorio).

## Artefatti diagnostici

In caso di fallimento di test/build, Actions carica artifact (retention 14 giorni
per i job obbligatori, 7 per EP00):

| Job | Artifact |
| --- | --- |
| `python-test` | `python-test-diagnostics-*` (`pytest-junit.xml`, `pytest.log`) |
| `js-test` | `js-test-diagnostics-*` (`js-test.log`) |
| `js-build` | `js-build-diagnostics-*` (`js-build.log`) |
| `ep00-extra-tests` | `ep00-test-diagnostics-*` |
| `performance-smoke` | `performance-smoke-*` (summary sanitizzati e metriche dello stack isolato) |

## Controllo migrazioni (EP01-06)

Alembic è configurato in `backend/alembic.ini`. ADR: [`ADR-0004`](../adr/ADR-0004-database-conventions.md).

`infra/scripts/check_migrations.py`:

- esce **1** se compaiono artifact orfani o layout incoerente;
- verifica `versions/`, single head, e — con `DATABASE_URL` — `alembic check` (drift);
- senza `DATABASE_URL` valida solo layout (utile in locale senza Docker).

Il job CI `migrations` è **obbligatorio**: Postgres effimero, `upgrade head`, drift check, pytest integration.

Test DB integration (skip senza `DATABASE_URL`):

```bash
export DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero
make migrate
cd backend && python -m pytest tests/integration/database -ra
```

## Test di accettazione

### Esecuzione completa su branch

1. Push su `dev` / `main` o apri una PR → workflow `CI` deve risultare verde.
2. In locale: `make quality` dalla root del monorepo.

### Test negativo controllato

Su un branch usa-e-getta, una modifica alla volta:

| Gate | Modifica voluta | Job che deve fallire |
| --- | --- | --- |
| Lint Python | `def _bad():\n    unused = 1` in un file sotto `backend/src` | `python-lint` |
| Format | es. `x=1+2` senza spazi (Ruff format) | `python-lint` (step format) |
| Test Python | `assert False` in `backend/tests/unit/test_health.py` | `python-test` (+ artifact) |
| Lint/typecheck JS | `const _ciBad: number = 'nope'` in `apps/web` | `js-lint` e/o `js-typecheck` |
| Test JS | assertion fallita in un `*.test.ts` | `js-test` (+ artifact) |
| Build | import rotto usato solo a build time | `js-build` (+ artifact) |
| Migrazioni | creare `backend/migrations/` vuota senza Alembic | `migrations` |

Ripristinare le modifiche dopo il test.

### Cache invalidata al cambio lockfile

1. Annotare nel log CI un hit di cache pnpm (`Cache restored from ...`).
2. Su un branch, bump innocuo di una dipendenza → aggiornare `pnpm-lock.yaml`.
3. Al run successivo la cache pnpm deve risultare **miss** / nuova chiave, poi
   ripopolarsi. Stesso ragionamento per `backend/pyproject.toml` e la cache pip.

## Relazioni

- Scaffold monorepo: [ADR-0003](../adr/ADR-0003-monorepo.md) (EP01-01)
- Ambiente locale Docker: [local_environment.md](local_environment.md) (EP01-02)
- Schema / Alembic: [ADR-0004](../adr/ADR-0004-database-conventions.md) (EP01-06)
