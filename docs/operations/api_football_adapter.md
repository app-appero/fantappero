# Adapter API-Football — EP04-01

| Metadato | Valore |
| --- | --- |
| Card | EP04-01 |
| Modulo | `backend/src/sports_data/provider/` |
| Provider | API-Football v3 |
| ADR | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md) |

## Ruolo

L’adapter SPD è l’**unico** componente autorizzato a chiamare API-Football. Autenticazione, paginazione, errori, retry, metriche e mapping envelope → DTO interni vivono qui. I client web/mobile e gli altri moduli di dominio **non** importano `httpx` verso il vendor né leggono `API_FOOTBALL_KEY`.

Fuori scope originario (card successive): sync catalogo (EP04-02 — [`sports_catalog_sync.md`](./sports_catalog_sync.md)), calciatori/rose (EP04-03), listone (EP04-04), fixture/eventi (EP04-05 — [`sports_fixtures_sync.md`](./sports_fixtures_sync.md)), scheduler (EP04-06 — [`sports_scheduler.md`](./sports_scheduler.md)).

## Configurazione

| Variabile | Default | Note |
| --- | --- | --- |
| `API_FOOTBALL_KEY` / `APISPORTS_KEY` | unset | Obbligatoria per istanziare il client; solo backend |
| `API_FOOTBALL_BASE_URL` | `https://v3.football.api-sports.io` | Override per stub/proxy locali |
| `API_FOOTBALL_TIMEOUT_SECONDS` | `30` | Timeout HTTP |
| `API_FOOTBALL_MAX_RETRIES` | `3` | Retry su 429 / 5xx / trasporto |
| `API_FOOTBALL_RETRY_BACKOFF_SECONDS` | `1` | Backoff esponenziale base |
| `API_FOOTBALL_REQUESTS_PER_MINUTE` | `300` | Throttle client (Piano Pro). A saturazione aspetta e riprende |
| `API_FOOTBALL_RATE_LIMIT_PAUSE_SECONDS` | `60` | Pausa su 429 / `errors.rateLimit` prima di riprendere |

Vedi anche [`configuration_and_secrets.md`](./configuration_and_secrets.md).

## Uso

```python
from config.settings import get_api_settings
from sports_data.provider import (
    ApiFootballClient,
    build_client_from_settings,
    map_competitions,
    store_provider_snapshot,
)

settings = get_api_settings()
with build_client_from_settings(settings) as client:
    envelope = client.get("/leagues", {"current": "true"})
    competitions = map_competitions(envelope)
    # Persistenza grezza auditabile (idempotente sul contenuto):
    # store_provider_snapshot(session, envelope)
```

Header autenticazione: `x-apisports-key` (mai loggato in chiaro — redaction EP01-04).

## Persistenza `provider_snapshots`

| Campo | Ruolo |
| --- | --- |
| `request_fingerprint` | Hash stabile endpoint + parametri (senza `page`) |
| `payload_hash` | SHA-256 del JSON canonico |
| Unique | `(provider, endpoint, request_fingerprint, payload_hash)` |

Stesso payload → nessuna nuova riga. Payload diverso stessa richiesta → nuova riga (storico), nessuna cancellazione.

## Metriche

| Nome | Tipo | Label |
| --- | --- | --- |
| `provider_requests_total` | counter | `provider`, `endpoint`, `status` |
| `provider_request_errors_total` | counter | `provider`, `endpoint`, `error_type` |
| `provider_request_duration_seconds` | histogram | `provider`, `endpoint` |
| `provider_retries_total` | counter | `provider`, `endpoint` |
| `provider_rate_limit_remaining` | gauge | `provider` |
| `provider_snapshots_stored_total` | counter | `provider`, `endpoint`, `result` |
| `provider_snapshots_deduped_total` | counter | `provider`, `endpoint` |

Log strutturati: `provider_request_ok`, `provider_auth_rejected`, `provider_snapshot_stored`, `provider_snapshot_deduped` — senza chiave API né PII.

## Verifica

```bash
# Unit (offline, fixture corpus EP00-02)
docker compose --env-file infra/local/.env.example run --rm api \
  python -m pytest tests/unit/sports_data/test_api_football_adapter.py -ra

# Integrazione snapshot + migrazioni (profilo test)
docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/sports_data tests/integration/database/test_migrations.py -ra'
```

## Troubleshooting

| Sintomo | Azione |
| --- | --- |
| `ProviderConfigError` all’avvio client | Impostare `API_FOOTBALL_KEY` nel `.env` di root / secret manager |
| `ProviderAuthError` | Chiave invalida o piano scaduto — non riprovare in loop |
| `ProviderRateLimitError` | Attendere reset giornaliero UTC; ridurre polling (piano EP00-04) |
| Snapshot non deduplicato | Verificare che il JSON sia canonico (`sort_keys`) prima dell’hash |

Piano quota/polling: [`api_football_polling_plan.md`](./api_football_polling_plan.md).
