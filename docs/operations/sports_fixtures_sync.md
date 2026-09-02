# Fixture, eventi, lineup e statistiche — EP04-05

| Metadato | Valore |
| --- | --- |
| Card | EP04-05 |
| Modulo | `backend/src/sports_data/fixtures/` |
| Dipendenze | EP00 (matrice/corpus/normalizzazione), EP01 (DB/observability), EP04-01 (adapter), EP04-02 (catalogo) |
| ADR | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md), [`../adr/ADR-0002-sports-event-precedence.md`](../adr/ADR-0002-sports-event-precedence.md) |

## Ruolo

Ingerisce in modo **idempotente** il calendario partite e i dettagli (eventi, lineup ufficiali, statistiche giocatore), con snapshot grezzi e normalizzazione scoring (EP00-03). Gli UUID interni restano stabili; le sync ripetute non duplicano eventi; le correzioni provider sono rilevate (update / retract / restore).

Fuori scope: scheduler polling oltre le sync on-demand (EP04-06 — [`sports_scheduler.md`](./sports_scheduler.md)), applicazione fantavoto / omologazione, API utente, injuries/availability.

## Entità

| Tabella | Chiave idempotenza | Fonte |
| --- | --- | --- |
| `fixtures` | `provider_id` | `/fixtures` |
| `match_events` | `provider_event_key` | `/fixtures/events` + normalizzazione scoring |
| `official_lineups` | `(fixture_id, club_id)` | `/fixtures/lineups` |
| `official_lineup_entries` | `(lineup_id, athlete_provider_id)` | startXI / substitutes |
| `player_match_stats` | `(fixture_id, athlete_provider_id)` | `/fixtures/players` |

`provider_event_key` riusa la composizione EP00-03 (`events|…|primary` per timeline; chiavi scoring con role `goal`/`assist` o prefisso `players|` per stats-only).

Eventi timeline assenti nel payload successivo vengono marcati `is_active=false` + `retracted_at` (correzione). Un re-sync che li riporta li riattiva (`events_corrected`).

Stagioni storiche assenti nel catalogo corrente possono essere **create al bisogno** (`is_current=false`) quando il calendario referencia un `season` non ancora in `sport_seasons`.

## Flusso

1. **Prerequisito:** catalogo competizioni/club sincronizzato (EP04-02).
2. Persistenza snapshot grezzo (opzionale, EP04-01).
3. Upsert `fixtures` da `/fixtures`.
4. Upsert eventi timeline + normalizzazione scoring; retract dei primary mancanti.
5. Upsert lineup e entry; upsert stats con `stats_hash` per rilevare correzioni.

```python
from sports_data.fixtures import FixtureDetailBatch, sync_fixtures
# sync_fixtures(session, fixtures_envelopes=[...], detail_batches=[...])
```

## Metriche e log

| Nome | Tipo | Label |
| --- | --- | --- |
| `fixture_sync_runs_total` | counter | `provider`, `status` |
| `fixture_sync_entities_total` | counter | `provider`, `entity`, `result` |
| `fixture_sync_duration_seconds` | histogram | `provider` |

`entity`: `fixtures` \| `events` \| `lineups` \| `lineup_entries` \| `stats` \| `athletes` \| `seasons`  
`result`: `created` \| `updated` \| `unchanged` \| `corrected` \| `retracted` \| `skipped_missing_club` \| …

Log strutturati: `fixture_sync_ok`, `fixture_sync_failed` — senza chiave API né PII.

## Operazioni

```bash
# Migrazioni
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

# Catalogo (prerequisito)
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_catalog.py --from-fixtures

# Fixture offline (match campione West Ham–Chelsea 1035055)
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_fixtures.py --from-fixtures

# Live (richiede API_FOOTBALL_KEY nel .env locale, non committare)
docker compose --env-file infra/local/.env.example run --rm api \
  python scripts/sync_sports_fixtures.py --from-provider --max-fixtures-per-league 5

# Task Celery on-demand (lo schedule automatico è EP04-06 — vedi sports_scheduler.md)
# sports_data.sync_mvp_fixtures
# sports_data.poll_live_window / poll_pre_match_window / poll_post_match_window / poll_late_corrections_window
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example run --rm api \
  python -m pytest tests/unit/sports_data/test_fixture_mapping.py -ra

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  python -m pytest tests/integration/sports_data/test_fixture_sync.py -ra
```

## Evidenza card EP04-05

- Sync ripetuta: UUID fixture stabili, `events_created=0` al secondo passaggio.
- Correzione: rimozione evento → `events_retracted`; modifica commenti/stats → `events_corrected` / `stats_corrected`.
- Mapping unitario su corpus EP00-02 (`matches/39/1035055`).
