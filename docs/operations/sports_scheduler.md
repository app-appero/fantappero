# Scheduler polling pre/live/post partita — EP04-06

| Metadato | Valore |
| --- | --- |
| Card | EP04-06 |
| Modulo | `backend/src/sports_data/scheduler/` |
| Dipendenze | EP00 (piano polling / quota), EP01 (Compose/worker/Redis/metriche), EP04-05 (sync fixture) |
| Piano quote | [`api_football_polling_plan.md`](./api_football_polling_plan.md) |
| ADR | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md) |

## Ruolo

Automatizza il **polling a finestre** (pre-partita, live, post-partita, correzioni tardive) con:

- **lock Redis** per evitare doppi job concorrenti sulla stessa finestra;
- **quote e modalità degradata** osservabili (`ok` / `warn` / `degrade` / `critical_only`);
- **retry** ereditati dal client SPD (EP04-01) + gate di intervallo allungato in degradazione;
- **audit** su tabella `sports_poll_runs`;
- **metriche e log** strutturati senza PII né chiavi API.

Fuori scope: omologazione fantavoto, API utente, predictions come fatti di scoring, injuries pipeline dedicata.

## Finestre

Allineate a [`api_football_polling_plan.md`](./api_football_polling_plan.md) e `tools/api_quota_estimator/config/default.json`:

| Finestra | Intervallo base | Lock TTL | Contenuto tipico |
| --- | --- | --- | --- |
| `pre_match` | 900s | 840s | calendario league+date, lineup vicino al kickoff |
| `live` | 60s | 55s | `/fixtures?live=all` + events per partita MVP |
| `post_match` | 600s | 540s | events + players (+ lineup catch-up) |
| `late_corrections` | 3600s | 3300s | re-fetch sparso events/players |

La classificazione usa `status_short` + `kickoff_at` (`classify_fixture_window`).

## Quote e degradazione

| Remaining / limit | Mode | Effetto |
| --- | --- | --- |
| > 25% | `ok` | intervalli base |
| ≤ 25% | `warn` | alert log; sync completa |
| ≤ 15% | `degrade` | intervallo ×2.5; drop criticality `low`; cap fixture; status `degraded_ok` |
| ≤ 5% | `critical_only` | solo high/critical; sospende `pre_match` (`skipped_quota`) |

Gauge `sports_scheduler_quota_mode` (0–3) espone la modalità corrente.

## Lock

Chiave Redis `sports:poll:lock:{window}` con `SET NX EX` e release confronta-token (Lua).  
Se il lock è occupato → status `skipped_lock`, metrica `sports_scheduler_lock_skipped_total`, **nessuna** seconda sync.

## Configurazione

| Variabile | Default | Note |
| --- | --- | --- |
| `SPORTS_SCHEDULER_ENABLED` | `false` | Abilita beat schedule; in locale resta spento per non consumare quota |
| `SPORTS_POLL_LIVE_INTERVAL_SECONDS` | `60` | |
| `SPORTS_POLL_PRE_INTERVAL_SECONDS` | `900` | |
| `SPORTS_POLL_POST_INTERVAL_SECONDS` | `600` | |
| `SPORTS_POLL_LATE_INTERVAL_SECONDS` | `3600` | |

Richiede `API_FOOTBALL_KEY` nel `.env` locale (non committare) quando lo scheduler è abilitato.

## Infrastruttura

Servizio Compose `beat` (Celery beat) oltre a `worker`:

```bash
docker compose --env-file infra/local/.env.example up -d --build beat worker
```

Con `SPORTS_SCHEDULER_ENABLED=true` in `infra/local/.env` il beat enqueua i task:

- `sports_data.poll_live_window`
- `sports_data.poll_pre_match_window`
- `sports_data.poll_post_match_window`
- `sports_data.poll_late_corrections_window`

## Metriche e log

| Nome | Tipo | Label |
| --- | --- | --- |
| `sports_scheduler_runs_total` | counter | `provider`, `window`, `status` |
| `sports_scheduler_duration_seconds` | histogram | `provider`, `window` |
| `sports_scheduler_fixtures_total` | counter | `provider`, `window`, `result` |
| `sports_scheduler_quota_mode` | gauge | `provider` |
| `sports_scheduler_lock_acquired_total` / `_skipped_total` / `_errors_total` | counter | `provider`, `lock` |
| `sports_scheduler_skipped_interval_total` | counter | `provider`, `window`, `quota_mode` |

Log: `sports_scheduler_ok`, `sports_scheduler_degraded`, `sports_scheduler_skipped`, `sports_scheduler_failed`, `sports_scheduler_lock_busy`.

## Operazioni

```bash
# Migrazione
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

# Task on-demand (anche con scheduler disabilitato)
docker compose --env-file infra/local/.env.example exec worker \
  celery -A app.worker.celery_app call sports_data.poll_live_window
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example run --rm api \
  python -m pytest tests/unit/sports_data/test_scheduler_policy.py -ra

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/sports_data/test_scheduler_poll.py -ra'
```

## Evidenza card EP04-06

- Lock: secondo ciclo concorrente → `skipped_lock`, nessuna doppia sync.
- Degradazione: remaining ≤15% → `degraded_ok` + `quota_mode=degrade` su `sports_poll_runs`.
- Idempotenza: due poll con payload campione West Ham–Chelsea (`matches/39/1035055`) → UUID fixture stabile, `fixtures_created=0` al secondo passaggio.
- Mapping: riuso test EP04-05 + classificazione finestre unitaria.
