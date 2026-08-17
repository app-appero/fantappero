# Voto statistico e fantavoto versionati — EP07-01 / EP07-02 / EP07-03

| Metadato | Valore |
| --- | --- |
| Card | EP07-01, EP07-02, EP07-03 |
| Modulo | `backend/src/fantasy_ratings/` |
| Dipendenze | EP00-05 (spike Rating Beta), EP04-05 (fixture/stats/eventi), EP06 (turni — contesto matchday) |
| Spike di riferimento | `experiments/rating_beta/` (`beta-v0.1`) |
| Requisiti | FR-SCO-01 (voto statistico), FR-SCO-02 (bonus/malus e fantavoto) |

## Ruolo

Persiste il **voto statistico FantApperò** per calciatore-partita con formula
**versionata**, **input** e **componenti** spiegabili (`fantasy_ratings/formula.py`):
base **6**, clamp **3–10**, pesi per ruolo P/D/C/A, gol/assist **esclusi** dal voto
statistico (contano solo nel bonus/malus, EP07-03).

La **soglia minuti** (EP07-02, `fantasy_ratings/eligibility.py`) è configurabile
per lega 1–30 (default 15, `league_rules.minutes_threshold`): sotto soglia il
calciatore resta senza voto salvo evento rilevante (gol, assist, rigore
sbagliato, autogol, espulsione) o portiere titolare.

Il **bonus/malus** (EP07-03, `fantasy_ratings/bonus.py`) applica gli eventi
ufficiali (FR-SCO-02) al voto statistico producendo il **fantavoto**.

Fuori scope: sostituzioni e formazione effettiva (EP07-04), punteggio squadra
e scontro diretto (EP07-05).

## Formula voto statistico `beta-v0.1`

| Parametro | Valore |
| --- | --- |
| `base` | 6.0 |
| `clamp` | 3.0 – 10.0 |
| `display_step` | 0.5 (solo se eleggibile) |
| Soglia minuti standard | 15, configurabile 1–30 per lega (`league_rules.minutes_threshold`) |
| Gol/assist in stats | mai componenti del voto statistico |

Ogni voto persistito contiene:

- `formula_json` — snapshot completo della versione usata;
- `input_json` — minuti, posizione, stats, flag evento rilevante, `stats_hash`;
- `components_json` — contributi per componente (`id`, `path`, `coeff`, `contribution`, …).

Il voto è ricostruibile come `clamp(base + Σ contributioni)`.

## Bonus e malus `bonus-beta-v0.1` (FR-SCO-02)

| Evento | Valore | Ruolo |
| --- | --- | --- |
| Gol | +3 | tutti |
| Assist | +1 | tutti |
| Ammonizione | −0,5 | tutti |
| Espulsione | −1 | tutti |
| Autogol | −2 | tutti |
| Rigore sbagliato | −3 | tutti |
| Rigore parato | +3 | solo P |
| Gol subito | −1 per gol | solo P |
| Porta inviolata | +1 | solo P (0 gol subiti) |

Regole:

- ogni componente legge un campo statistico aggregato già deduplicato dal
  provider (o un conteggio di `match_event` attivi con `provider_event_key`
  univoco per l'autogol): nessun evento è contato due volte;
- un rigore segnato è già incluso in `goals.total` (bonus gol), non riceve un
  bonus "rigore segnato" separato, per non duplicare l'evento;
- **decisione aperta** (FR-SCO-02, da chiudere nel regolamento esecutivo):
  doppia ammonizione/espulsione nello stesso episodio. Default Beta
  `red_supersedes_yellow` — si applica solo il malus espulsione;
- il bonus/malus si applica solo se il voto statistico è eleggibile (EP07-02);
  un calciatore senza voto non riceve bonus/malus.

Ogni voto persistito contiene inoltre:

- `bonus_malus_json` — componenti bonus/malus (`id`, `count`, `unit_value`, `contribution`);
- `bonus_malus_total` — somma dei componenti;
- `fantasy_score` — `display + bonus_malus_total` (fantavoto), `null` se non eleggibile;
- `bonus_config_version` — versione della configurazione bonus/malus usata.

## Entità

| Tabella | Vincoli | Note |
| --- | --- | --- |
| `player_match_ratings` | unique `(fixture_id, athlete_provider_id, formula_version)` | Upsert idempotente per hash stats; colonne bonus/malus aggiunte in EP07-03 |

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
`experiments/rating_beta/tests/test_golden.py`, esteso in EP07-03 con casi
bonus/malus reali (rigore parato/sbagliato, autogol, doppia ammonizione ed
espulsione) sulla stessa fixture.

## Relazioni

- Spike offline: [`experiments/rating_beta/README.md`](../../experiments/rating_beta/README.md)
- Fixture sync: [`../operations/sports_fixtures_sync.md`](../operations/sports_fixtures_sync.md)
- Turni europei: [`fantasy_turns.md`](./fantasy_turns.md)
