# Listone ufficiale e ruoli P–D–C–A — EP04-04

| Metadato | Valore |
| --- | --- |
| Card | EP04-04 |
| Modulo | `backend/src/sports_data/listone/` |
| Dipendenze | EP00 (matrice/fixture/OQ-01), EP01 (DB/observability), EP04-03 (athletes/squad_memberships) |
| ADR | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md) |

## Ruolo

Genera il **listone ufficiale** della piattaforma: ogni calciatore con membership attiva riceve un ruolo FantApperò valido **P / D / C / A**. Le leghe possono applicare **override pre-asta** (effetto immediato); dopo l’avvio stagione le modifiche decorrono dal **turno successivo**.

Fuori scope: persistenza fixture/eventi (EP04-05 — [`sports_fixtures_sync.md`](./sports_fixtures_sync.md)), scheduler polling (EP04-06), asta/rose fantasy complete.

## Mapping posizione → ruolo (OQ-01)

Versione corrente: `v1.0.0` (`sports_data.listone.mapping.MAPPING_VERSION`).

| Posizione provider (normalizzata) | Ruolo |
| --- | --- |
| Goalkeeper, G, GK, Keeper | P |
| Defender, D, Defence/Defense | D |
| Midfielder, M, Midfield | C |
| Attacker, Forward, F, Striker | A |

Posizioni ambigue non mappate (es. Wing Back) restano fuori listone (`skipped_unmapped`) fino a override operativo / bump mapping.

## Entità

| Tabella | Chiave idempotenza | Note |
| --- | --- | --- |
| `role_assignments` | `(athlete_id, season_year)` | Ruolo ufficiale piattaforma |
| `league_role_overrides` | un solo attivo per `(league_id, athlete_id)` (`superseded_at IS NULL`) | Override lega versionato |

`effective_from_round`:
- `NULL` — immediato (pre-asta / da inizio stagione)
- `N` — applicabile dal turno `N` in poi

## API lega

| Metodo | Percorso | Permesso |
| --- | --- | --- |
| `GET` | `/leagues/{id}/listone?currentRound=` | `league:view` |
| `POST` | `/leagues/{id}/amministrazione/listone/aggiorna` | `league:admin` |
| `PUT` | `/leagues/{id}/amministrazione/listone/{athleteId}/ruolo` | `league:admin` |
| `DELETE` | `/leagues/{id}/amministrazione/listone/{athleteId}/ruolo` | `league:admin` |

`POST …/aggiorna` (async): **sempre** sync catalogo MVP → `sync_mvp_roster_with_client(season_year)`
(API-Football, tutte le rose dei club censiti) → `generate_official_listone`.
Progresso pollabile su `GET …/aggiorna/{jobId}` (`percent` 0–100).
Richiede `API_FOOTBALL_KEY` sul backend e worker Celery.
Il sync non è esposto in UI Asta/Rosa (ruolo operatore / pannello qualità dati — EP04-07 / EP11-04);
in locale si usano gli script sotto.

Audit: `league_role_override_set` / `league_role_override_cleared` / `league_listone_refreshed`.

## Metriche e log

| Nome | Tipo | Label |
| --- | --- | --- |
| `listone_generate_runs_total` | counter | `provider`, `status` |
| `listone_generate_entities_total` | counter | `provider`, `result` |
| `listone_generate_duration_seconds` | histogram | `provider` |
| `listone_unmapped_positions_total` | counter | `provider` |
| `listone_override_writes_total` | counter | `provider`, `action` |
| `listone_refresh_runs_total` | counter | `provider`, `status` |
| `listone_refresh_duration_seconds` | histogram | `provider` |

Log: `listone_generate_ok`, `listone_generate_failed`, `listone_position_unmapped`, `listone_override_set`, `listone_override_cleared`, `listone_refresh_ok`, `listone_refresh_failed` — senza PII/segreti.

## Operazioni

```bash
# Migrazioni
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

# Prerequisiti: catalogo + roster
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_catalog.py --from-fixtures
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_roster.py --from-fixtures

# Generazione listone
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/generate_sports_listone.py --season-year 2026

# Task Celery on-demand: sports_data.generate_official_listone
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example run --rm api \
  python -m pytest tests/unit/sports_data/test_listone_mapping.py tests/unit/sports_data/test_listone_validators.py tests/unit/leagues/test_listone_refresh.py -ra

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/sports_data/test_listone.py tests/integration/database/test_migrations.py -ra'

# Web Asta listone
docker compose --env-file infra/local/.env.example run --rm web \
  pnpm --filter @fantappero/web test -- src/pages/AuctionPage.test.tsx src/App.wireframes.test.tsx
```

## Troubleshooting

| Sintomo | Azione |
| --- | --- |
| `skipped_unmapped` > 0 | Verificare `provider_position_raw`; aggiornare mapping versionato o correggere roster |
| `athlete_not_on_listone` | Eseguire generazione listone dopo sync roster |
| Override non applicato in lega attiva | Controllare `effectiveFromRound` vs `currentRound` (decorre dal turno successivo) |

Roster: [`sports_roster_sync.md`](./sports_roster_sync.md) · Catalogo: [`sports_catalog_sync.md`](./sports_catalog_sync.md).
