# backend

Backend **FastAPI** FantApperò: moduli di dominio, adapter (SPD / API-Football), migrazioni, worker asincroni.

Path kept as `backend/` (not `apps/api/`) — see [`docs/adr/ADR-0003-monorepo.md`](../docs/adr/ADR-0003-monorepo.md).

## Stack previsto

Python 3.12+, FastAPI, PostgreSQL, Redis/Celery (come da Architettura MVP).

## Layout

```text
backend/
  src/app/           # FastAPI (health + auth EP02-01)
  src/auth/          # Email/password, sessions, rate limits — EP02-01
  src/database/      # SQLAlchemy base, session, baseline models — EP01-06
  src/sports_data/   # SPD anti-corruption (normalizzazione eventi EP00-03)
  alembic/           # Migrazioni Alembic (EP01-06)
  alembic.ini
  scripts/           # tool offline sport data (EP00)
  tests/             # unit + integration/database
  pyproject.toml     # pinned deps + pytest pythonpath=src
```

## Scaffold commands (no secrets required)

```bash
python -m pip install -e "./backend[dev]"
cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# GET http://127.0.0.1:8000/health → {"status":"ok"} (deps skipped if URL unset)
python -m pytest tests/unit/test_health.py
```

### Stack locale Docker (EP01-02)

API e worker condividono `infra/local/Dockerfile`. Compose root: `compose.yaml`.

```bash
# dalla root del monorepo
make up && make health
# worker: celery -A app.worker.celery_app
```

Vedi [`docs/development/local_environment.md`](../docs/development/local_environment.md).

### Database e migrazioni (EP01-06)

Con Postgres avviato (`make up`) e `DATABASE_URL` in `.env`:

```bash
make migrate              # alembic upgrade head
make migrate-check        # verifica drift (alembic check)
cd backend && python -m pytest tests/integration/database -ra
```

Convenzioni: [`docs/adr/ADR-0004-database-conventions.md`](../docs/adr/ADR-0004-database-conventions.md).

## Confini

- Unica sede delle chiavi provider (via env / secret manager).
- I client (`apps/*`) non chiamano API-Football.
- Identificativi provider restano nell’anti-corruption layer (ADR-0001).

## Tool sport data (EP00)

```bash
# dalla root del monorepo
python backend/scripts/validate_sports_dataset.py
python backend/scripts/acquire_sports_dataset.py --from-manifest

# test (corpus + normalizzazione eventi)
python -m pytest backend/tests -q

# quota / polling plan (EP00-04)
python -m pytest tools/api_quota_estimator -q
python -m api_quota_estimator --csv docs/operations/api_quota_scenarios.csv
# (cwd: tools/api_quota_estimator)
```

`API_FOOTBALL_KEY` vive nel `.env` di root (o env di processo), mai nei client.

Precedenza eventi fantavoto: [`docs/data/event_precedence_rules.md`](../docs/data/event_precedence_rules.md), ADR-0002.

Polling e dimensionamento piano API: [`docs/operations/api_football_polling_plan.md`](../docs/operations/api_football_polling_plan.md).

### Auth (EP02-01)

Email/password, sessioni bearer revocabili, verifica email, reset password, rate limit.

```bash
make migrate
python -m pytest tests/unit/auth -q
# Integration (Postgres): DATABASE_URL=... python -m pytest tests/integration/auth -q
```

Documentazione: [`docs/development/auth.md`](../docs/development/auth.md).

Rating Beta sperimentale (EP00-05, offline, no DB):

```bash
cd experiments/rating_beta
python -m rating_beta
python -m pytest
```

Config: [`experiments/rating_beta/config/beta-v0.1.yaml`](../experiments/rating_beta/config/beta-v0.1.yaml) · Report: [`experiments/rating_beta/reports/rating_beta_v0.1.md`](../experiments/rating_beta/reports/rating_beta_v0.1.md).
