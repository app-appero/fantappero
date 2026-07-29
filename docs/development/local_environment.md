# Ambiente locale (EP01-02)

Stack riproducibile con Docker Compose: **PostgreSQL**, **Redis**, **API**, **worker** Celery e **web** (Vite). Mobile resta su host (`pnpm dev:mobile`).

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

# Avvia solo il web (richiede postgres/redis/api già up, o usa il comando sopra)
# docker compose --env-file infra/local/.env.example up -d --build web

# Verifica healthy
./infra/scripts/dev_healthcheck.sh
# oppure: make health
```

Atteso: `postgres`, `redis`, `api`, `worker`, `web` in stato **healthy**. Apri il client su `http://127.0.0.1:5173` (o `WEB_PORT` se override).

Smoke automatico (persistenza volumi + errore se manca Postgres):

```bash
./infra/scripts/smoke_local_stack.sh
# oppure: make smoke-local
```

## Servizi essenziali vs strumenti opzionali

| Profilo | Servizi | Comando |
| --- | --- | --- |
| Default (essenziali) | `postgres`, `redis`, `api`, `worker`, `web` | `make up` |
| `tools` (opzionale) | `adminer`, `redis-commander` | `make up-tools` |

Gli strumenti opzionali **non** sono richiesti per lo sviluppo. **Mobile** (Expo) non è in Compose: avvialo sull’host con `pnpm dev:mobile` quando serve.

## Porte

| Servizio | Host | Container | Note |
| --- | --- | --- | --- |
| Web (Vite) | `5173` | `5173` | Auth UI; `VITE_API_BASE_URL` punta all’API su host |
| API | `8000` | `8000` | `GET /live`, `GET /ready` (alias `GET /health`) |
| PostgreSQL | `5432` | `5432` | user/db `fantappero` |
| Redis | `6379` | `6379` | AOF abilitato |
| Adminer | `8081` | `8080` | solo profile `tools` |
| Redis Commander | `8082` | `8081` | solo profile `tools` |

Override porte via `infra/local/.env` (`API_PORT`, `WEB_PORT`, `POSTGRES_PORT`, …).

## Credenziali locali (non di produzione)

Valori di default in `infra/local/.env.example`:

- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` = `fantappero` / `fantappero_local_dev_only` / `fantappero`
- `DATABASE_URL` → host Compose `postgres`
- `REDIS_URL` / `CELERY_*` → host Compose `redis`

Non inserire chiavi provider reali (`API_FOOTBALL_KEY`, ecc.) nei file commitati. Per host-run dell’API contro i container, copia root `.env.example` → `.env` e usa gli URL `127.0.0.1` documentati lì.

**Attenzione:** Compose legge il `.env` di root solo per la **sostituzione variabili** (`${…}`). Il root `.env` con `DATABASE_URL=…@127.0.0.1` serve all’API **sull’host**; i container `api`/`worker` usano hostname `postgres`/`redis` (vedi `compose.yaml`).

## Comandi

| Azione | Script | Make | Docker Compose |
| --- | --- | --- | --- |
| Start | `./infra/scripts/dev_up.sh` | `make up` | `docker compose --env-file infra/local/.env.example up -d --build` |

Usa **`up -d --build` senza nome servizio** per avviare postgres, redis, api, worker e web insieme.  
`up web` da solo può fallire se postgres/redis sono spenti (errore `container … exited (0)`).
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
| `fantappero_redis_data` | Persistenza Redis (AOF) |
| `fantappero_web_node_modules` | `node_modules` root del container web |
| `fantappero_web_app_node_modules` | dipendenze Linux di `apps/web` (non usare quelle Windows dell’host) |
| `fantappero_web_contracts_node_modules` | dipendenze workspace `packages/contracts` |
| `fantappero_web_ui_node_modules` | dipendenze workspace `packages/ui` |

`make down` / `docker compose stop` **non** li elimina. Solo `dev_reset.sh` / `down -v`.

## Layout file

```text
compose.yaml                 # stack locale
infra/local/Dockerfile       # immagine condivisa API + worker
infra/local/Dockerfile.web   # dev server Vite (web)
infra/local/.env.example     # default senza segreti reali
infra/scripts/dev_*.sh             # start / stop / logs / reset / health
infra/scripts/smoke_local_stack.sh # smoke + persistenza + missing-dep
docs/development/local_environment.md
```

## Web su host (alternativa a Compose)

Se preferisci Vite sull’host (HMR più veloce su Windows nativo), **non** avviare il servizio `web` in Compose — ferma solo quel container e usa:

```bash
docker compose --env-file infra/local/.env.example up -d postgres redis api worker
pnpm dev:web
```

Non tenere `pnpm dev:web` e il container `web` attivi insieme: entrambi usano la porta **5173**.

## API su host + sole dipendenze in Docker

```bash
docker compose --env-file infra/local/.env.example up -d postgres redis
# in .env di root (non commitare):
# DATABASE_URL=postgresql://fantappero:fantappero_local_dev_only@127.0.0.1:5432/fantappero
# REDIS_URL=redis://127.0.0.1:6379/0
make dev-api
```

## Migrazioni database (EP01-06)

Con **Compose**, l’API applica automaticamente `alembic upgrade head` all’avvio (`infra/scripts/dev_api_entrypoint.sh`). Dopo un pull con nuove migration basta:

```powershell
docker compose --env-file infra/local/.env.example up -d --build
```

Migrazioni manuali (solo se serve, es. API su host):

```bash
# Linux / macOS — API su host con DATABASE_URL verso 127.0.0.1 (root .env)
make migrate

# Windows (Compose): rete Docker, non la porta 5432 dell'host
.\infra\scripts\migrate.ps1
# oppure: bash infra/scripts/migrate_docker.sh
# oppure: make migrate-docker   # richiede Git Bash / WSL

make migrate-check
cd backend && python -m pytest tests/integration/database -ra
```

**Windows:** `python -m alembic upgrade head` dalla cartella `backend/` spesso fallisce con `autenticazione con password fallita` perché `127.0.0.1:5432` può puntare a un Postgres diverso da quello di Compose. Con Compose usa `up --build`; altrimenti `migrate.ps1`.

Convenzioni e rollback: [`docs/adr/ADR-0004-database-conventions.md`](../adr/ADR-0004-database-conventions.md).

## Risoluzione problemi comuni

| Sintomo | Cosa controllare |
| --- | --- |
| `docker daemon not reachable` | Avviare Docker Desktop / il servizio Docker |
| Porta già in uso (`5432` / `6379` / `8000`) | Fermare il processo host o cambiare `*_PORT` in `infra/local/.env` |
| `api` unhealthy / `/health` 503 | `docker compose logs api`; verificare che `postgres` e `redis` siano healthy |
| `worker` unhealthy | Log Celery: `./infra/scripts/dev_logs.sh worker`; Redis deve accettare connessioni |
| Build lenta o cache stantia | `docker compose build --no-cache api` |
| Script `.sh` su Windows PowerShell | Usare Git Bash, WSL, o i comandi `docker compose` / `make` equivalenti |
| `alembic` / `make migrate` → password fallita (Windows) | Usare `.\infra\scripts\migrate.ps1` — migra via rete Docker (`postgres`) |
| Register/login → `relation "users" does not exist` | Migrations non applicate: `.\infra\scripts\migrate.ps1` |
| Reset rifiutato | Impostare esplicitamente `CONFIRM=yes` |
| Dati “spariti” dopo reset | Atteso: `down -v` cancella i volumi nominati |

## Test di accettazione (manuale / CI locale)

1. Clone pulito → `./infra/scripts/dev_up.sh` → tutti healthy.
2. `./infra/scripts/smoke_local_stack.sh` → smoke, persistenza, 503 senza Postgres, refuse reset.
3. `CONFIRM=yes ./infra/scripts/dev_reset.sh` → volumi rimossi; `dev_up` riparte a vuoto.

Quality gates (lint / test / build, senza Docker): vedi [`quality_gates.md`](quality_gates.md) e `make quality`.
