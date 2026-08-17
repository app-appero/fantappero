# Voto statistico versionato — EP07-01

| Metadato | Valore |
| --- | --- |
| Card | EP07-01 |
| Modulo | `backend/src/fantasy_ratings/` |
| Dipendenze | EP00-05 (spike Rating Beta), EP04-05 (fixture/stats), EP06 (turni — contesto matchday) |
| Spike di riferimento | `experiments/rating_beta/` (`beta-v0.1`) |

## Ruolo

Persiste il **voto statistico FantApperò** per calciatore-partita con formula
**versionata**, **input** e **componenti** spiegabili. Il motore è puro
(`fantasy_ratings/formula.py`): base **6**, clamp **3–10**, pesi per ruolo P/D/C/A,
gol/assist **esclusi** dal voto statistico (bonus/malus in EP07-03).

Fuori scope: bonus/malus (EP07-03), soglia minuti configurabile per lega
(EP07-02), sostituzioni e formazione effettiva (EP07-04), punteggio H2H
(EP07-05).

## Formula `beta-v0.1`

| Parametro | Valore |
| --- | --- |
| `base` | 6.0 |
| `clamp` | 3.0 – 10.0 |
| `display_step` | 0.5 (solo se eleggibile) |
| Soglia minuti (transitoria) | 15 (allineata allo spike EP00-05; EP07-02 la renderà configurabile) |
| Gol/assist in stats | mai componenti |

Ogni voto persistito contiene:

- `formula_json` — snapshot completo della versione usata;
- `input_json` — minuti, posizione, stats, flag evento rilevante, `stats_hash`;
- `components_json` — contributi per componente (`id`, `path`, `coeff`, `contribution`, …).

Il voto è ricostruibile come `clamp(base + Σ contributioni)`.

## Entità

| Tabella | Vincoli | Note |
| --- | --- | --- |
| `player_match_ratings` | unique `(fixture_id, athlete_provider_id, formula_version)` | Upsert idempotente per hash stats |

## API (permesso `global:operate`)

| Metodo | Path | Descrizione |
| --- | --- | --- |
| `POST` | `/fantasy-ratings/compute` | Calcola e persiste i voti di una fixture |
| `GET` | `/fantasy-ratings/fixtures/{fixtureId}` | Elenco voti con formula, input e componenti |

Body compute (uno dei due campi):

```json
{ "fixtureProviderId": 1035055 }
```

Risposta:

```json
{
  "fixtureId": "…",
  "fixtureProviderId": 1035055,
  "formulaVersion": "beta-v0.1",
  "created": 22,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "votes": 22
}
```

## Job asincrono

Task Celery: `fantasy_ratings.compute_fixture`

Argomenti opzionali: `fixture_id` (UUID string) oppure `fixture_provider_id` (int).

## Metriche

| Nome | Label | Significato |
| --- | --- | --- |
| `fantasy_ratings_compute_runs_total` | `version`, `result` | Esecuzioni compute |
| `fantasy_ratings_compute_votes_total` | `result` | created/updated/unchanged/removed |
| `fantasy_ratings_compute_duration_seconds` | `version` | Durata compute |

## Verifica

```bash
docker compose --env-file infra/local/.env.example --profile test up -d postgres-test

docker compose --env-file infra/local/.env.example run --rm api sh -lc \
  'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/fantasy_ratings tests/integration/fantasy_ratings -ra'

docker compose --env-file infra/local/.env.example run --rm api sh -lc \
  'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/integration/database/test_migrations.py -ra'
```

Golden test: stesso sottoinsieme del corpus EP00-02 (`1035055`) dello spike
`experiments/rating_beta/tests/test_golden.py`.

## Relazioni

- Spike offline: [`experiments/rating_beta/README.md`](../../experiments/rating_beta/README.md)
- Fixture sync: [`../operations/sports_fixtures_sync.md`](../operations/sports_fixtures_sync.md)
- Turni europei: [`fantasy_turns.md`](./fantasy_turns.md)
