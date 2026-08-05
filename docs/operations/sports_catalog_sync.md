# Catalogo competizioni e stagioni — EP04-02

| Metadato | Valore |
| --- | --- |
| Card | EP04-02 |
| Modulo | `backend/src/sports_data/catalog/` |
| Dipendenze | EP00 (fixture/matrice), EP01 (DB/observability), EP04-01 (adapter) |
| ADR | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md) |

## Ruolo

Sincronizza in modo **idempotente** i cinque campionati MVP, le relative stagioni e i club (squadre) nel database applicativo. Gli UUID interni restano stabili: la chiave esterna è sempre `provider_id` (API-Football).

Fuori scope: calciatori/trasferimenti (EP04-03), listone (EP04-04), fixture persistite (EP04-05 — [`sports_fixtures_sync.md`](./sports_fixtures_sync.md)), scheduler di polling (EP04-06).

## Entità

| Tabella | Chiave idempotenza | Fonte |
| --- | --- | --- |
| `competitions` (EP03-01) | `provider_id` unico | `/leagues` |
| `sport_seasons` | `(competition_id, year)` | `/leagues` → `seasons[]` |
| `clubs` | `provider_id` unico | `/teams` |
| `competition_season_clubs` | `(sport_season_id, club_id)` | membership stagione |

Le nazionali (`team.national=true`) sono scartate al sync (MVP = solo club di campionato).

## Flusso

1. Persistenza snapshot grezzo (opzionale, riusa EP04-01).
2. Upsert competizioni MVP (`MVP_LEAGUE_IDS`: 39, 140, 135, 78, 61).
3. Upsert stagioni con flag `coverage.*`.
4. Per ogni competizione/stagione corrente: upsert club + membership.

```python
from sports_data.catalog import sync_catalog, TeamsBatch
from sports_data.provider import parse_envelope, build_client_from_settings
from sports_data.catalog import sync_mvp_catalog_with_client

# Offline (fixture)
# sync_catalog(session, leagues_envelope=..., teams_batches=[TeamsBatch(...)])

# Live
# with build_client_from_settings(settings) as client:
#     sync_mvp_catalog_with_client(session, client)
```

## Metriche e log

| Nome | Tipo | Label |
| --- | --- | --- |
| `catalog_sync_runs_total` | counter | `provider`, `status` |
| `catalog_sync_entities_total` | counter | `provider`, `entity`, `result` |
| `catalog_sync_duration_seconds` | histogram | `provider` |

`entity`: `competitions` \| `seasons` \| `clubs` \| `memberships`  
`result`: `created` \| `updated` \| `unchanged` \| `skipped_national`

Log strutturati: `catalog_sync_ok`, `catalog_competitions_seasons_synced`, `catalog_clubs_synced`, `catalog_sync_failed` — senza chiave API né PII.

## Operazioni

```bash
# Migrazioni
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

# Sync offline da corpus EP00-02
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_catalog.py --from-fixtures

# Sync live (richiede API_FOOTBALL_KEY nel .env locale, non committare)
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_catalog.py --from-provider

# Task Celery on-demand (non schedulato — EP04-06)
# sports_data.sync_mvp_catalog
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example run --rm api \
  python -m pytest tests/unit/sports_data/test_catalog_mapping.py -ra

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/sports_data/test_catalog_sync.py tests/integration/database/test_migrations.py -ra'
```

## Troubleshooting

| Sintomo | Azione |
| --- | --- |
| `ValueError` stagione assente | Eseguire prima sync competizioni/stagioni (`/leagues`) |
| `ProviderConfigError` | Impostare `API_FOOTBALL_KEY` solo per `--from-provider` |
| UUID competizione cambiato | Non dovrebbe accadere: verificare unique su `provider_id` e assenza di delete/recreate |

Adapter HTTP: [`api_football_adapter.md`](./api_football_adapter.md).
