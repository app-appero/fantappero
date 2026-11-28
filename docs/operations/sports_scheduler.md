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

**Da dove viene la quota** (dal 24/11). A ogni giro una sonda `GET /status` (non consuma quota) legge dal corpo `response.requests.current` e `limit_day`: sono le chiamate di oggi dell'intero account, quindi anche quelle dell'altro ambiente sulla stessa chiave. Se il corpo non le porta restano gli header `x-ratelimit-requests-*`. Rimasto e limite finiscono in `sports_poll_runs.details` (`quota_remaining`, `quota_limit`). Prima la sonda falliva sempre, perché `/status` risponde con un oggetto e non con una lista: la modalità restava `ok` anche a quota quasi finita, e il 23/11 la quota del giorno è finita senza nessun freno.

**Quota del giorno finita.** API-Football risponde 200 con `errors.requests` («You have reached the request limit for the day…») fino alla mezzanotte UTC. Ora è un errore a parte, `ProviderDailyLimitError` (codice `provider_daily_limit_reached`, sottotipo di `ProviderRateLimitError`), senza pause né nuovi tentativi: aspettare un minuto non serve. Log `provider_daily_limit_reached endpoint=… code=…`. Nel Riepilogo operatore il motivo è «quota giornaliera finita». Se lo dice già la sonda, la modalità passa a `critical_only`.

**Correzioni tardive.** Il giro chiede al massimo 15 partite (7 in degradazione). A parità di stato vengono prima le partite ancora senza statistiche dei giocatori di entrambe le squadre, cioè senza voti.

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

Log: `sports_scheduler_ok`, `sports_scheduler_degraded`, `sports_scheduler_skipped`, `sports_scheduler_failed`, `sports_scheduler_lock_busy`, `sports_scheduler_status_probe_failed`, `sports_scheduler_status_probe_daily_limit`.

Il formatter dei log del worker Celery scarta i campi `extra`. Per questo i log da leggere hanno i dati essenziali anche nel testo, per esempio:
- `sports_scheduler_status_probe_failed window=live error=ProviderResponseError`;
- `sports_scheduler_failed window=post_match quota_mode=ok error=ProviderDailyLimitError`;
- `fantasy_live_pipeline_round_skipped round_id=… league_id=… code=calendar_not_found` (oppure `_round_failed … code=<tipo di eccezione>`).

Nel risultato del task, `fantasy_pipeline.errors` è una lista di righe di testo nello stesso formato: prima Celery mostrava solo `errors: [{...}]`.

## Operazioni

```bash
# Migrazione
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

# Task on-demand (anche con scheduler disabilitato)
docker compose --env-file infra/local/.env.example exec worker \
  celery -A app.worker.celery_app call sports_data.poll_live_window
```

## Lancio a mano dal pannello operatore (1.5)

Operatore › **Job**: «Esegui» su ogni job e «Esegui tutti» (solo i job accesi); Operatore › **Turni**: «Esegui tutti». Tutti chiedono «Sei sicuro?» e avvisano quando un giro usa la quota del fornitore sportivo (campo `uses_provider_quota` del catalogo `system_jobs/catalog.py`).

- **Job** (`POST /admin/job/{chiave}/esegui`, `POST /admin/job/esegui-tutti`, solo `global:operate`): mandano al worker lo stesso task del beat con i `kwargs` di catalogo; frequenze e orari non cambiano. Un job spento si lancia lo stesso, una volta sola e con un avviso (`allow_periodic` lo lascia passare perché il lancio è segnato come manuale, senza toccare `last_started_at`). Ogni lancio scrive una riga di audit di piattaforma (`league_audit_events`, `league_id` nullo, azione `system_job_run_manual`: chi, quando, quale job).
- **Doppio lancio:** il job si prenota su Redis (`fantappero:system_jobs:running:<chiave>`, `SET NX` con scadenza 30 minuti, `system_jobs/running.py`); il worker segna e toglie lo stesso segno a ogni giro, anche del beat, e lo toglie dopo aver scritto l'esito in `system_job_runs`. Un job già in esecuzione risponde 409 (`system_job_already_running`), in «Esegui tutti» è «già in esecuzione, non rilanciato». Senza Redis il lancio a mano è rifiutato (503). `GET /admin/job` dice `running` e `lastRun`.
- **Turni** (`POST /admin/turni/esegui-tutti`, avanzamento con `GET …/{id}`): un task Celery (`admin.run_turni_batch`) lancia in sequenza Importa calendario stagione, Genera calendario, Sincronizza turni, Aggiorna probabili e Genera formazioni IA (le stesse logiche dei pulsanti «Azioni massive»); un errore non ferma le altre. Restano fuori «Calcola giornata corrente» e «Recupera risultati» (omologano i turni), «Ricalcola storico» (riapre turni omologati e avvisa gli utenti) e le azioni per singola lega. Un solo blocco alla volta (`fantappero:admin:turni_batch:lock`, 409 `turni_batch_already_running`); un'operazione si salta se il job automatico che fa la stessa cosa sta girando.
- Un job che richiedesse argomenti non sarebbe lanciabile a mano: `tests/unit/system_jobs/test_manual_run_catalog.py` controlla che ogni task del catalogo parta con i soli `kwargs` di catalogo.

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
