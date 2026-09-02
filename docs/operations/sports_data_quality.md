# Pannello qualità dati sportivi — EP04-07

| Metadato | Valore |
| --- | --- |
| Card | EP04-07 |
| Modulo | `backend/src/sports_data/quality/` |
| Dipendenze | EP00 (corpus/normalizzazione), EP01 (DB/observability/authz), EP04-05 (fixture persistite) |
| ADR | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md), [`../adr/ADR-0002-sports-event-precedence.md`](../adr/ADR-0002-sports-event-precedence.md) |

## Ruolo

Espone all’**operatore globale** una vista API-first di qualità della fonte sportiva centrale:

- **mancanti** — fixture FT senza eventi / lineup / stats;
- **ritardi** — PST, kickoff scaduto ancora NS/TBD;
- **conflitti** — eventi con `anomaly_codes` o status `anomaly|provisional|insufficient`;
- **correzioni** — eventi ritirati (`is_active=false`).

Consentire di **individuare** i gap e **rilanciare** una sync fixture trasparente (fetch provider o corpus offline in test), con audit su `sports_data_sync_retries` e senza edit manuali opachi.

Fuori scope: UI completa operatore (EP11-04), omologazione fantavoto, job di scoring.

## Modello

| Tabella | Chiave | Note |
| --- | --- | --- |
| `sports_data_quality_issues` | `fingerprint` unique | Upsert idempotente allo scan; status `open\|resolved\|dismissed` |
| `sports_data_sync_retries` | UUID | Audit rilancio: status, counters, error_code |

Fingerprint: `{code}:{fixture_provider_id}:{entity_ref}` (es. `missing_events:1035055:fixture`).

## API (permesso `global:operate`)

| Metodo | Path | Descrizione |
| --- | --- | --- |
| `GET` | `/sports-data/quality/summary` | Aggregati open / kind / severity |
| `GET` | `/sports-data/quality/issues` | Elenco issue (`kind`, `status`, paginazione) |
| `POST` | `/sports-data/quality/scan` | Scan idempotente (opz. `fixtureId`) |
| `POST` | `/sports-data/quality/issues/{id}/retry-sync` | Rilancio sync della fixture collegata |
| `POST` | `/sports-data/quality/retry-sync` | Rilancio per `fixtureProviderId` |
| `GET` | `/sports-data/quality/retries` | Storico rilanci |

Messaggi e titoli issue in **italiano** (codici macchina stabili per futura i18n).

## Metriche e log

| Nome | Tipo | Label |
| --- | --- | --- |
| `sports_data_quality_scan_runs_total` | counter | `provider`, `status` |
| `sports_data_quality_scan_issues_total` | counter | `provider`, `result`, `kind` |
| `sports_data_quality_scan_duration_seconds` | histogram | `provider` |
| `sports_data_quality_open_issues` | gauge | `provider` |
| `sports_data_quality_retry_runs_total` | counter | `provider`, `status` |
| `sports_data_quality_retry_duration_seconds` | histogram | `provider` |

Log: `sports_data_quality_scan_ok` / `_failed`, `sports_data_quality_retry_ok` / `_failed` — senza PII né chiavi API.

## Operazioni

```bash
# Migrazione
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

# Scan on-demand (Celery)
docker compose --env-file infra/local/.env.example exec worker \
  celery -A app.worker.celery_app call sports_data.scan_quality

# Verifica unit + integration
docker compose --env-file infra/local/.env.example run --rm api \
  python -m pytest tests/unit/sports_data/test_quality_rules.py -ra

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/sports_data/test_quality_panel.py -ra'
```

## Runbook operatore

1. `POST /sports-data/quality/scan` — aggiorna le issue aperte.
2. `GET /sports-data/quality/issues?status=open` — individua gap (kind/code/fixtureProviderId).
3. `POST /sports-data/quality/issues/{id}/retry-sync` — rilancia sync provider per quella fixture.
4. Controllare `status`/`counters` nella risposta e, se necessario, ripetere lo scan: issue risolte passano a `resolved`.
5. Se `errorCode=provider_unavailable` → verificare `API_FOOTBALL_KEY` nel `.env` locale (non committare).

## Evidenza card EP04-07

- Scan ripetuto: fingerprint stabili, `issues_created=0` al secondo passaggio.
- Retry offline su corpus West Ham–Chelsea (`matches/39/1035055`): sync idempotente + risoluzione `missing_events`.
- Mapping: riuso envelope EP00-02 / sync EP04-05.
