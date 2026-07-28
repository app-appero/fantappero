# Dataset coverage — API-Football offline corpus (EP00-02)

| Metadato | Valore |
| --- | --- |
| Versione dataset | 0.2.0 |
| Freeze | 2026-07-27T14:48:04Z |
| Card | EP00-02 |
| Dipendenza | EP00-01 |
| Root | `backend/tests/fixtures/api_football/` |
| Validazione | `python backend/scripts/validate_sports_dataset.py` |

## Provenienza

Corpus **provider v3** acquisito con `GET /fixtures?ids=` (batch fino a 20) da `https://v3.football.api-sports.io`, con events/lineups/players embedded quando disponibili. Payload sanitizzati/minimizzati (niente media URL, niente header/auth). Provenienza e checksum in `manifest.json` + `checksums.sha256`.

Refresh (richiede rete + chiave; i test CI non lo eseguono):

```bash
python backend/scripts/acquire_sports_dataset.py --from-manifest --enrich-rare
python backend/scripts/validate_sports_dataset.py
```

Chiave: `API_FOOTBALL_KEY` nel `.env` di root (mai commit).

## Contenuto

| Voce | Valore |
| --- | --- |
| Fixture | 20 partite `FT`, 4 per campionato |
| Campionati | 39 Premier League, 140 La Liga, 135 Serie A, 78 Bundesliga, 61 Ligue 1 |
| Endpoint per match | `/fixtures`, `/fixtures/events`, `/fixtures/lineups`, `/fixtures/players` |
| Reference | `/leagues`, `/teams` (club del campione) |

### Casi rari

Stato autorevole in `manifest.json → coverage` (snapshot v0.2.0):

| Caso | Stato |
| --- | --- |
| Rigore segnato / sbagliato / parato | Trovati |
| Espulsione | Trovato |
| Sostituzione | Trovato (tutte le 20) |
| Clean sheet | Trovato |
| Autogol (`Own Goal`) | Trovato (fixture 718611) |
| Rinvio (`PST`) | **Non reperito** (scan big-5 stagione 2024 vuoto; i PST riprogrammati spesso spariscono dallo status) |
| Correzione post-partita | **Non reperito** (serve doppio snapshot nel tempo) |

### Endpoint EP00-01 non nel freeze match

Elencati in `coverage.endpoints_not_reperito`: `/players`, `/players/squads`, `/injuries`, `/transfers`, `/standings`, `/predictions`. Fuori scope del campione partite; da acquisire in card dedicate listone/IA.

## Layout deterministico

```text
backend/tests/fixtures/api_football/
  manifest.json
  checksums.sha256
  reference/leagues.json
  reference/teams.json
  matches/{league_id}/{fixture_id}/fixtures.json
  matches/{league_id}/{fixture_id}/fixtures_events.json
  matches/{league_id}/{fixture_id}/fixtures_lineups.json
  matches/{league_id}/{fixture_id}/fixtures_players.json
```

## Comandi

```bash
# Offline (test / CI)
python backend/scripts/validate_sports_dataset.py
python -m pytest backend/tests/test_sports_dataset.py -q

# Refresh provider (dev only)
python backend/scripts/acquire_sports_dataset.py --from-manifest --enrich-rare
python backend/scripts/validate_sports_dataset.py
```

## Criteri di accettazione EP00-02

| Criterio | Come verificato |
| --- | --- |
| ≥20 fixture e 5 campionati | `validate_sports_dataset.py` |
| Casi rari coperti o `not_found` | `manifest.coverage` |
| Test solo file locali | validazione e pytest senza HTTP |
| No secret | scan pattern + assenza header |
| Naming/checksum | path deterministici + `checksums.sha256` + no dir orfane |
