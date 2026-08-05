# FantApperò

Fantacalcio europeo a scontri diretti, basato sui cinque principali campionati (Premier League, LaLiga, Serie A, Bundesliga, Ligue 1), con formazione progressiva, mosse tattiche e staff IA solo consultivo.

## Di cosa parla il progetto

FantApperò porta il fantacalcio tradizionale italiano in una dimensione europea, senza meccaniche pay-to-win. Le leghe sono private (4–10 partecipanti, 8 consigliati), con rose esclusive da 35 calciatori (3P–11D–11C–10A) e budget Standard di 1.000 crediti.

### Pilastri
- **Europa** — listone e partite dei cinque big campionati
- **Strategia** — formazione progressiva, 7 moduli, 3 mosse tattiche per turno, fino a 5 sostituzioni automatiche
- **Libertà** — asta a buste, inserimento manuale o import CSV (asta live in Fase 2)
- **Trasparenza** — FantApperò Rating Beta spiegabile e versionato + bonus/malus separati
- **IA utile** — Viceallenatore, Osservatore e Analista propongono; conferma sempre umana
- **Equità** — nessun acquisto può alterare crediti, mosse, sostituzioni o punteggi

### MVP in sintesi
- Leghe private a scontri diretti (niente playoff)
- Turni europei autonomi (non legati alle giornate nazionali)
- Mercato: svincolati a buste, scambi, gestione admin
- Dati sportivi da API-Football, normalizzati e riusati da tutte le leghe
- Stack previsto: React/React Native, FastAPI, PostgreSQL, Redis/Celery

## Struttura monorepo

| Percorso | Ruolo |
| --- | --- |
| [`backend`](backend) | FastAPI — BE, dominio, adapter SPD, migrazioni, worker |
| [`apps/web`](apps/web) | React (Vite) web + futuro pannello admin |
| [`apps/mobile`](apps/mobile) | React Native / Expo |
| [`packages/contracts`](packages/contracts) | Tipi / contratti condivisi (futura OpenAPI) |
| [`packages/ui`](packages/ui) | Design token e primitive presentazionali |
| [`infra`](infra) | Docker, ambienti, CI/CD |
| [`tools`](tools) | Utility operative (quota API EP00-04) |
| [`experiments`](experiments) | Prototipi offline (Rating Beta EP00-05) |
| [`docs`](docs) | ADR, matrici dati, operazioni, decisioni di prodotto |

Decisione di layout: [`docs/adr/ADR-0003-monorepo.md`](docs/adr/ADR-0003-monorepo.md).  
Il percorso API resta `backend/` (non `apps/api/`) per coordinamento con EP00.

I client (`apps/*`) non contengono chiavi provider. I segreti (es. `API_FOOTBALL_KEY`) restano nel `.env` di root o nel secret manager, usati solo da `backend`. **Il bootstrap scaffold (EP01-01) non richiede segreti né servizi cloud.**

### Confini di dipendenza

```text
apps/web ──┐
apps/mobile┼──► packages/contracts
           └──► packages/ui
backend  (Python) ──► sports_data / app   [no import da apps o packages JS]
```

Niente dipendenze circolari: i pacchetti non importano le app; le app non importano moduli Python.

## Prerequisiti

| Tool | Versione |
| --- | --- |
| Python | ≥ 3.12 |
| Node.js | ≥ 20 |
| pnpm | 9.x (`corepack enable` oppure `npm i -g pnpm@9`) |
| Docker | Engine/Desktop + Compose v2 (stack locale EP01-02) |
| Make | opzionale (GNU Make); su Windows usare i comandi `pnpm` / `python` / `docker compose` sotto |
| Bash | per `infra/scripts/*.sh` (Git Bash / WSL su Windows) |

## Setup da clone pulito

```bash
# JavaScript workspace (lockfile: pnpm-lock.yaml)
pnpm install

# Backend Python (dipendenze pinnate in backend/pyproject.toml)
python -m pip install -e "./backend[dev]"
```

Equivalente: `make setup` (se Make è disponibile).

### Ambiente locale containerizzato (EP01-02)

Da macchina pulita con Docker:

```bash
./infra/scripts/dev_up.sh          # oppure: make up
./infra/scripts/dev_healthcheck.sh # postgres, redis, api, worker, web → healthy
```

| Azione | Comando |
| --- | --- |
| Start essenziali | `make up` / `./infra/scripts/dev_up.sh` |
| Stop (volumi intatti) | `make down` / `./infra/scripts/dev_down.sh` |
| Log | `make logs` / `./infra/scripts/dev_logs.sh` |
| Health | `make health` |
| Reset **distruttivo** dati | `CONFIRM=yes make reset-local` |
| Smoke stack | `make smoke-local` |
| Tools opzionali (Adminer, Redis Commander) | `make up-tools` |

Porte default: API `8000`, Web `5173`, PostgreSQL `5432`, Redis `6379`.  
Dettagli, troubleshooting e volumi: [`docs/development/local_environment.md`](docs/development/local_environment.md).

I default in `infra/local/.env.example` sono placeholder locali, non segreti di produzione.

## Sviluppo

| Target | Comando |
| --- | --- |
| Stack Docker (API+worker+Postgres+Redis+Web) | `make up` poi `http://127.0.0.1:5173` e `http://127.0.0.1:8000/health` |
| API host-only | `make dev-api` oppure `cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| Web host-only (`http://127.0.0.1:5173`) | `make dev-web` oppure `pnpm dev:web` |
| Mobile (Expo) | `make dev-mobile` oppure `pnpm dev:mobile` |

## Test / lint / build (quality gates EP01-03)

```bash
# Parità con CI (lint, format, typecheck, test, build, migrations check)
make quality

# Gate singoli
make test          # oppure: cd backend && python -m pytest ; pnpm test
make lint
make format        # ruff format --check
make typecheck
make build
make check-migrations
make smoke         # test + build (subset)
```

Smoke individuali:

```bash
cd backend && python -m pytest tests/unit/test_health.py
pnpm --filter @fantappero/web test
pnpm --filter @fantappero/mobile test
pnpm run build:packages
```

Dettaglio job CI, cache, artefatti e test negativi:
[`docs/development/quality_gates.md`](docs/development/quality_gates.md).

## Documentazione di prodotto

Specifiche in `doc_fantapperò` (Documento Master, Requisiti funzionali MVP, Architettura e modello dati).
