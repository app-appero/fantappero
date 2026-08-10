# Ambiente locale (EP01-02)

Stack riproducibile con Docker Compose: **PostgreSQL**, **Redis**, **API**, **worker** Celery e **web** (Vite).

## Prerequisiti

| Tool | Note |
| --- | --- |
| Docker Engine / Desktop | Con plugin Compose v2 (`docker compose version`) |
| Bash | Per gli script in `infra/scripts/` (Git Bash / WSL su Windows) |
| Make | Opzionale; i comandi equivalenti sono sotto |

Non servono segreti reali: i default in `infra/local/.env.example` sono solo placeholder locali.

## Avvio da macchina pulita

Dalla root del monorepo:

```bash
# Opzionale: override locali (gitignored)
cp infra/local/.env.example infra/local/.env

# Build + start servizi essenziali
./infra/scripts/dev_up.sh
# oppure: make up
# oppure: docker compose --env-file infra/local/.env.example up -d --build

# Verifica healthy
./infra/scripts/dev_healthcheck.sh
# oppure: make health
```

Atteso: `postgres`, `redis`, `api`, `worker`, `web` in stato **healthy**.  
Servizio opzionale per lo schedule sportivo: `beat` (Celery beat, EP04-06 — abilitare con `SPORTS_SCHEDULER_ENABLED=true`).

App web: `http://localhost:5174` (API su `http://localhost:8001`).

Smoke automatico (persistenza volumi + errore se manca Postgres):

```bash
./infra/scripts/smoke_local_stack.sh
# oppure: make smoke-local
```

## Servizi essenziali vs strumenti opzionali

| Profilo | Servizi | Comando |
| --- | --- | --- |
| Default (essenziali) | `postgres`, `redis`, `api`, `worker`, `web`, `mailpit` | `docker compose --env-file infra/local/.env.example up -d --build` |
| `test` | PostgreSQL isolato `fantappero_test` | `docker compose --profile test up -d postgres-test` |
| `tools` (opzionale) | `adminer`, `redis-commander` | `make up-tools` |

Gli strumenti opzionali **non** sono richiesti per lo sviluppo API/worker.

## Porte

| Servizio | Host | Container | Note |
| --- | --- | --- | --- |
| API | `8001` | `8001` | `GET /live`, `GET /ready` (alias `GET /health`) |
| Web (Vite) | `5174` | `5174` | hot reload con mount sorgenti |
| PostgreSQL | `5432` | `5432` | user/db `fantappero` |
| Redis | `6379` | `6379` | AOF abilitato |
| Mailpit UI | `8025` | `8025` | Web UI email di test |
| Mailpit SMTP | `1025` | `1025` | Invio email auth locale |
| Adminer | `8081` | `8080` | solo profile `tools` |
| Redis Commander | `8082` | `8081` | solo profile `tools` |

Override porte via `infra/local/.env` (`API_PORT`, `WEB_PORT`, `POSTGRES_PORT`, …).

## Credenziali locali (non di produzione)

Valori di default in `infra/local/.env.example`:

- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` = `fantappero` / `fantappero_local_dev_only` / `fantappero`
- `DATABASE_URL` → host Compose `postgres`
- `REDIS_URL` / `CELERY_*` → host Compose `redis`

Non inserire chiavi provider reali (`API_FOOTBALL_KEY`, ecc.) nei file commitati. Per host-run dell’API contro i container, copia root `.env.example` → `.env` e usa gli URL `127.0.0.1` documentati lì.

### Verifica email in locale (EP02-01)

1. Avvia lo stack con Mailpit incluso.
2. Registrati da `http://localhost:5174/accedi/registrati`.
3. Apri `http://localhost:8025` e segui il link di verifica nell’email catturata.
4. Accedi da `/accedi`.

## Comandi

| Azione | Script | Make | Docker Compose |
| --- | --- | --- | --- |
| Start | `./infra/scripts/dev_up.sh` | `make up` | `docker compose --env-file infra/local/.env.example up -d --build` |
| Stop (volumi intatti) | `./infra/scripts/dev_down.sh` | `make down` | `docker compose stop` |
| Log | `./infra/scripts/dev_logs.sh [svc…]` | `make logs` | `docker compose logs -f` |
| Health | `./infra/scripts/dev_healthcheck.sh` | `make health` | — |
| Reset **distruttivo** | `CONFIRM=yes ./infra/scripts/dev_reset.sh` | `make reset-local CONFIRM=yes` | `docker compose down -v` |
| Tools opzionali | — | `make up-tools` | `docker compose --profile tools up -d` |

### Reset dati

Il reset **cancella i volumi nominati** `fantappero_pg_data` e `fantappero_redis_data`.

Senza `CONFIRM=yes` il comando **esce con errore** (protezione anti-cancellazione accidentale).

```bash
CONFIRM=yes ./infra/scripts/dev_reset.sh
```

## Volumi nominati

| Volume | Contenuto |
| --- | --- |
| `fantappero_pg_data` | Dati PostgreSQL |
| `fantappero_pg_test_data` | Database isolato e distruttibile per i test d'integrazione |
| `fantappero_redis_data` | Persistenza Redis (AOF) |
| `fantappero_web_node_modules` | `node_modules` del container web (pnpm) |

`make down` / `docker compose stop` **non** li elimina. Solo `dev_reset.sh` / `down -v`.

## Layout file

```text
compose.yaml                 # stack locale
infra/local/Dockerfile       # immagine condivisa API + worker
infra/local/Dockerfile.web   # dev server Vite
infra/local/.env.example     # default senza segreti reali
infra/scripts/dev_*.sh             # start / stop / logs / reset / health
infra/scripts/smoke_local_stack.sh # smoke + persistenza + missing-dep
docs/development/local_environment.md
```

## API su host + sole dipendenze in Docker

```bash
docker compose --env-file infra/local/.env.example up -d postgres redis
# in .env di root (non commitare):
# DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero
# REDIS_URL=redis://127.0.0.1:6379/0
make dev-api
```

## Migrazioni database (EP01-06)

Dopo `make up`, applicare lo schema baseline:

```bash
# Schema del database di sviluppo
docker compose --env-file infra/local/.env.example run --rm api alembic upgrade head
docker compose --env-file infra/local/.env.example run --rm api alembic check

# Test distruttivi esclusivamente sul database dedicato
docker compose --env-file infra/local/.env.example --profile test up -d postgres-test redis mailpit
docker compose --env-file infra/local/.env.example --profile test run --rm api sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/database -ra'
```

Le fixture d'integrazione rifiutano qualsiasi database il cui nome non termini con
`_test`. Questa protezione impedisce downgrade o cancellazioni accidentali sul database
di sviluppo `fantappero`.

Convenzioni e rollback: [`docs/adr/ADR-0004-database-conventions.md`](../adr/ADR-0004-database-conventions.md).

## Risoluzione problemi comuni

| Sintomo | Cosa controllare |
| --- | --- |
| `docker daemon not reachable` | Avviare Docker Desktop / il servizio Docker |
| Porta già in uso (`5432` / `6379` / `8001` / `5174`) | Fermare il processo host o cambiare `*_PORT` in `infra/local/.env` |
| `api` unhealthy / `/health` 503 | `docker compose logs api`; verificare che `postgres` e `redis` siano healthy |
| `worker` unhealthy | Log Celery: `./infra/scripts/dev_logs.sh worker`; Redis deve accettare connessioni |
| Build lenta o cache stantia | `docker compose build --no-cache api` |
| Script `.sh` su Windows PowerShell | Usare Git Bash, WSL, o i comandi `docker compose` / `make` equivalenti |
| Reset rifiutato | Impostare esplicitamente `CONFIRM=yes` |
| Dati “spariti” dopo reset | Atteso: `down -v` cancella i volumi nominati |

## Test di accettazione (manuale / CI locale)

1. Clone pulito → `./infra/scripts/dev_up.sh` → tutti healthy.
2. `./infra/scripts/smoke_local_stack.sh` → smoke, persistenza, 503 senza Postgres, refuse reset.
3. `CONFIRM=yes ./infra/scripts/dev_reset.sh` → volumi rimossi; `dev_up` riparte a vuoto.

Quality gates (lint / test / build, senza Docker): vedi [`quality_gates.md`](quality_gates.md) e `make quality`.
