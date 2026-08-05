# Calciatori, rose reali e trasferimenti — EP04-03

| Metadato | Valore |
| --- | --- |
| Card | EP04-03 |
| Modulo | `backend/src/sports_data/roster/` |
| Dipendenze | EP00 (matrice/fixture), EP01 (DB/observability), EP04-01 (adapter), EP04-02 (catalogo club/stagioni) |
| ADR | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md) |

## Ruolo

Sincronizza in modo **idempotente** anagrafiche calciatori, appartenenze di rosa per stagione e storico trasferimenti. Gli UUID interni restano stabili; i cambi squadra **non eliminano** membership storiche.

Fuori scope: mapping ruoli P–D–C–A e listone fantasy (EP04-04 — vedi [`sports_listone.md`](./sports_listone.md)), fixture persistite (EP04-05 — [`sports_fixtures_sync.md`](./sports_fixtures_sync.md)), scheduler polling (EP04-06).

## Entità

| Tabella | Chiave idempotenza | Fonte |
| --- | --- | --- |
| `athletes` | `provider_id` unico | `/players`, `/players/squads` |
| `squad_memberships` | `(athlete_id, club_id, sport_season_id)` | `/players/squads`, `/players?team&season` |
| `transfers` | `provider_key` (atleta+data+club+tipo) | `/transfers` |

Trasferimenti con tipo `Loan` o `N/A` impostano `requires_admin_review=true` (OQ-12, FR-MKT-02).

## Flusso

1. **Prerequisito:** catalogo competizioni/stagioni/club sincronizzato (EP04-02).
2. Persistenza snapshot grezzo (opzionale, riusa EP04-01).
3. Upsert atleti e membership da `/players/squads` e/o `/players`.
4. Upsert trasferimenti; chiusura membership origine (`is_active=false`, `ended_at`) e apertura destinazione.

```python
from sports_data.roster import SquadBatch, PlayersBatch, sync_roster
from sports_data.provider import parse_envelope

# sync_roster(session, squad_batches=[...], players_batches=[...], transfers_envelopes=[...])
```

## Metriche e log

| Nome | Tipo | Label |
| --- | --- | --- |
| `roster_sync_runs_total` | counter | `provider`, `status` |
| `roster_sync_entities_total` | counter | `provider`, `entity`, `result` |
| `roster_sync_duration_seconds` | histogram | `provider` |

`entity`: `athletes` \| `memberships` \| `transfers`  
`result`: `created` \| `updated` \| `unchanged` \| `deactivated` \| `skipped_missing_club`

Log strutturati: `roster_sync_ok`, `roster_squads_synced`, `roster_players_synced`, `roster_transfers_synced`, `roster_sync_failed` — senza chiave API né PII.

## Operazioni

```bash
# Migrazioni
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

# Catalogo (prerequisito)
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_catalog.py --from-fixtures

# Roster offline da corpus EP04-03
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_roster.py --from-fixtures

# Live (richiede API_FOOTBALL_KEY nel .env locale, non committare)
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_roster.py --from-provider

# Task Celery on-demand (non schedulato — EP04-06)
# sports_data.sync_mvp_roster
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example run --rm api \
  python -m pytest tests/unit/sports_data/test_roster_mapping.py tests/unit/sports_data/test_roster_validators.py -ra

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/sports_data/test_roster_sync.py tests/integration/database/test_migrations.py -ra'
```

## Troubleshooting

| Sintomo | Azione |
| --- | --- |
| `memberships_skipped_missing_club` | Eseguire sync catalogo club (EP04-02) |
| `memberships_skipped_missing_season` | Sincronizzare stagioni per la competizione |
| Trasferimento Loan in coda admin | Atteso: `requires_admin_review=true`; risolvere manualmente (FR-MKT-02) |
| UUID atleta cambiato | Verificare unique su `athletes.provider_id` |

Catalogo club: [`sports_catalog_sync.md`](./sports_catalog_sync.md) · Adapter HTTP: [`api_football_adapter.md`](./api_football_adapter.md).
