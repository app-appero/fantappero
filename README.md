# FantApperò

Piattaforma fantasy football (fantacalcio) multipiattaforma: backend FastAPI/PostgreSQL, web app React, app mobile Expo/React Native, integrazione centralizzata con API-Football.

## Stato attuale

**Beta tecnicamente avanzata, Fase 1 non ancora chiusa formalmente.** La maggior parte delle funzionalità MVP è implementata (leghe, rose, crediti, asta, mercato, formazioni con lock, calendario H2H, scoring, classifiche, notifiche, funzioni AI, osservabilità, backup/DR). Non è ancora stato eseguito un pilot reale con utenti esterni né registrata una decisione GO/NO-GO.

Il piano operativo per arrivare alla chiusura verificabile della Fase 1 è in: [`docs/FantAppero_Piano_Chiusura_Fase_1.md`](docs/FantAppero_Piano_Chiusura_Fase_1.md).
Lo stato riga per riga di ogni requisito è tracciato in: [`docs/operations/registro_requisiti_fase1.md`](docs/operations/registro_requisiti_fase1.md) — **bozza di prima passata**, non ancora verificata con evidenze manuali complete.

**Limiti noti della release corrente** (vedi registro per il dettaglio):

- l'E2E critico in CI è solo *informativo* (non blocca il merge) e copre solo 2 flussi web; non esiste ancora un E2E mobile automatizzato;
- 9 domande aperte su dati reali API-Football restano senza esito (minuti/recupero, copertura sui 5 campionati, infortuni/squalifiche, trasferimenti, porta inviolata, tra le altre) — vedi [`docs/data/api_football_open_questions.md`](docs/data/api_football_open_questions.md);
- il pilot reale con leghe esterne non è mai stato eseguito (solo un dry-run interno) — vedi [`docs/operations/beta_pilot_gate.md`](docs/operations/beta_pilot_gate.md).

## Architettura

Monolite modulare API-first in monorepo pnpm, orchestrato con Docker Compose:

| Componente | Percorso | Stack |
|---|---|---|
| Backend API | `backend/` | Python, FastAPI, SQLAlchemy, Alembic, Celery |
| Web app | `apps/web/` | React, TypeScript, Vite |
| App mobile | `apps/mobile/` | Expo, React Native, TypeScript |
| Test E2E | `apps/e2e/` | Playwright |
| Pacchetti condivisi | `packages/` | contratti TS, client API, design system UI |
| Infrastruttura locale | `infra/` | Docker Compose, script di avvio/healthcheck/backup |

Servizi runtime: PostgreSQL, Redis, worker/beat Celery per i processi asincroni (sincronizzazione dati sportivi, notifiche, email).

## Avvio locale

Prerequisiti: Docker Engine/Desktop con plugin Compose v2, Bash (Git Bash/WSL su Windows), Node ≥ 20, pnpm 9, Python ≥ 3.12.

```bash
# Setup dipendenze (Node + Python)
make setup

# Stack Docker: postgres, redis, api, worker, web, mailpit
cp infra/local/.env.example infra/local/.env   # opzionale, per override locali
./infra/scripts/dev_up.sh                      # oppure: make up

# Verifica servizi healthy
./infra/scripts/dev_healthcheck.sh             # oppure: make health
```

Web app: `http://localhost:5174` — API: `http://localhost:8001` (`GET /live`, `GET /ready`) — Mailpit (email di test): `http://localhost:8025`.

Guida completa, porte, profili opzionali (`tools`, `test`) e credenziali locali: [`docs/development/local_environment.md`](docs/development/local_environment.md).

Avvio app mobile: `pnpm dev:mobile` (Expo).

## Variabili d'ambiente

Nessun segreto reale richiesto in locale. Template:

- root `.env.example` → copia in `.env` per eseguire l'API sull'host contro i container Docker;
- `infra/local/.env.example` → override dello stack Compose;
- per-componente: `config/settings/`.

Dettagli su segreti e configurazione: [`docs/operations/configuration_and_secrets.md`](docs/operations/configuration_and_secrets.md).

**Non committare mai `.env`** né chiavi provider reali (es. `API_FOOTBALL_KEY`).

## Comandi di test e qualità

```bash
make quality        # tutti i gate obbligatori: lint, format, typecheck, test, build, check-migrations
make test            # pytest backend + test JS
make test-api         # solo pytest backend
make test-js          # solo test workspace JS
make lint / make typecheck / make build
```

Gate CI obbligatori vs informativi (inclusi E2E, performance): [`docs/development/quality_gates.md`](docs/development/quality_gates.md).

## Distinzione demo/reale

La modalità `?persona=` nella web app è **esclusivamente per sviluppo locale (DEV)**: simula un utente senza passare da un'autorizzazione server-side reale e non deve mai comparire in un ambiente pilot o di produzione. Ogni azione mostrata come riuscita nell'interfaccia deve corrispondere a una risposta reale del backend, autorizzata server-side — mai a uno stato simulato lato client.

## Struttura della documentazione

Indice completo e ordine di precedenza tra le fonti (in caso di contraddizione): [`docs/README.md`](docs/README.md).

Punti di partenza principali:

- [`docs/operations/`](docs/operations/) — processo Beta/pilot, sicurezza, backup/DR, supporto, qualità dati sportivi
- [`docs/adr/`](docs/adr/) — decisioni architetturali (ADR)
- [`docs/api/`](docs/api/) — contratti e comportamento degli endpoint
- [`docs/data/`](docs/data/) — regole sui dati sportivi e domande aperte sul provider
- [`docs/doc_fantapperò/`](docs/doc_fantapperò/) — documenti fondativi (Concept, Documento Master, Requisiti Funzionali, Architettura Tecnica) e pacchetti card per milestone

## Contribuire senza introdurre nuovo scope

Il repository è in fase di chiusura della Fase 1, non di sviluppo di nuove funzionalità (vedi [`docs/FantAppero_Piano_Chiusura_Fase_1.md`](docs/FantAppero_Piano_Chiusura_Fase_1.md), capitolo 7 "Cose da non fare in questa fase"). Prima di una modifica:

1. verifica lo stato del requisito nel [registro](docs/operations/registro_requisiti_fase1.md);
2. se il codice/test/UI esiste già, non riscriverlo: completa solo ciò che manca per chiudere il gap documentato;
3. ogni modifica con esperienza utente/admin deve avere comportamento equivalente su web e mobile, salvo `N/A mobile` motivato;
4. non introdurre funzionalità nuove non richieste da un gap MVP già tracciato — proponile invece come voce di backlog Fase 2.
