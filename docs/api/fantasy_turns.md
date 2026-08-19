# Turni europei — EP06-01

| Metadato | Valore |
| --- | --- |
| Card | EP06-01, EP06-07 |
| Modulo | `backend/src/fantasy_turns/` |
| Dipendenze | EP04-05 (fixture), EP05-05 (composizione rosa — pattern motore) |
| FR | FR-TUR-01, cutoff/stato minimi di FR-TUR-02, rinvii/variazioni orario |

## Ruolo

Genera e consulta il **turno europeo FantApperò**: raggruppa le fixture reali dei
campionati selezionati dalla lega in una finestra temporale autonoma (weekend
ven–lun o infrasettimanale mar–gio, timezone `Europe/Rome`), calcola il **cutoff**
come primo kickoff incluso e espone uno **stato effettivo** coerente anche quando
gli orari provider cambiano.

I turni sono **calcolati automaticamente** dal sistema per le leghe `active`
(job Celery `fantasy_turns.ensure_upcoming`, default orario; anche dopo sync
fixture MVP). Lo stesso job ricalcola cutoff e latch dei turni già materializzati
quando il provider sposta un orario. L’admin può forzare `POST …/turni/sincronizza`
o `POST …/ricalcola-cutoff`. La generazione manuale resta disponibile come
strumento avanzato.

Il motore regole puro (`fantasy_turns/rules.py` + `@fantappero/contracts` `fantasyTurns`)
è condiviso tra API e UI; le decisioni autoritative restano sul server.

Fuori scope: mosse scoring/risultati. Il lock per-calciatore è in [`fantasy_lineups.md`](./fantasy_lineups.md)
(EP06-03). I moduli, lo schieramento e le tre mosse tattiche (EP06-05) sono nello
stesso documento. I rinvii e le variazioni orario (EP06-07) ricalcolano il cutoff
senza sbloccare lock o mosse già consumate.

## Entità

| Tabella | Vincoli | Note |
| --- | --- | --- |
| `fantasy_rounds` | unique `(league_id, number)` | `kind` weekend/midweek; `status` scheduled/open/locked/skipped |
| `fantasy_round_fixtures` | unique `(round_id, fixture_id)`; unique parziale attiva `(league_id, fixture_id)` | Soft-exclude via `excluded_at`; `observed_kickoff_at` / `lock_latched_at` per rinvii (EP06-07) |
| `league_rules.min_fixtures_per_round` | 10–40, default 25 | Soglia Standard Master §5.1 |

## Regole

| Tema | Comportamento |
| --- | --- |
| Finestra weekend | Ven 00:00 → Mar 00:00 (esclusivo) Europe/Rome |
| Finestra midweek | Mar 00:00 → Ven 00:00 (esclusivo) Europe/Rome |
| Eleggibilità | Campionati della lega + `season_year`, kickoff in finestra, status ≠ `CANC`, non già assegnata |
| Soglia | Se count &lt; min → turno `skipped` con motivo visibile |
| Cutoff | `min(kickoff_at)` delle fixture ancora live; kickoff simultanei → stesso cutoff |
| Rinvio / cambio orario | Cutoff può slittare in avanti solo se l'istante precedente **non** è ancora trascorso. Dopo il cutoff originale, un orario più tardi **non** riapre la finestra. |
| Lock fixture | Alla prima scadenza dell'orario osservato (o status live/FT) il lock si **aggancia** (`lock_latched_at`). PST/CANC prima di quell'istante restano sbloccati. |
| Mosse già consumate | Il ricalcolo non rimborsa né cancella `tactical_moves` già applicate. |
| Stato effettivo | `open` + `now >= cutoff` → trattato come `locked` |
| Mutazioni | Esclusione/rigenerazione solo in `scheduled` |

## API

| Metodo | Percorso | Permesso |
| --- | --- | --- |
| `GET` | `/leagues/{id}/turni` | `matchday:view` |
| `GET` | `/leagues/{id}/turni/{roundId}` | `matchday:view` (ricalcola cutoff in lettura) |
| `POST` | `/leagues/{id}/turni/sincronizza` | `league:admin` — assicura turni upcoming (idempotente, auto-open) |
| `POST` | `/leagues/{id}/turni/anteprima` | `league:admin` |
| `POST` | `/leagues/{id}/turni` | `league:admin` — genera manuale (scheduled o skipped) |
| `POST` | `/leagues/{id}/turni/{roundId}/apri` | `league:admin` |
| `POST` | `/leagues/{id}/turni/{roundId}/escludi-fixture` | `league:admin` |
| `POST` | `/leagues/{id}/turni/{roundId}/ricalcola-cutoff` | `league:admin` |

Body generazione/anteprima:

```json
{ "kind": "weekend", "anchorDate": "2026-08-15" }
```

## UI

- Web `/turni` — lista/dettaglio, stato partita (rinviata/in corso), sync automatico admin, ricalcolo cutoff; tab Risultati placeholder.
- Mobile tab Turni — stessi flussi essenziali, con avviso se un rinvio non sblocca un kickoff già trascorso.

## Verifica

```bash
docker compose --env-file infra/local/.env.example build api
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/fantasy_turns tests/integration/fantasy_turns -ra'
```

## Automazione

| Env | Default | Ruolo |
| --- | --- | --- |
| `FANTASY_TURNS_AUTO_GENERATE_ENABLED` | `true` | Abilita beat + enqueue post-sync fixture |
| `FANTASY_TURNS_AUTO_GENERATE_INTERVAL_SECONDS` | `3600` | Frequenza job |
| `FANTASY_TURNS_HORIZON_DAYS` | `14` | Orizzonte weekend/midweek da materializzare |

Task: `fantasy_turns.ensure_upcoming` — solo leghe `active`; non persiste `skipped` in attesa di più partite (riprova al giro successivo); auto-apre i turni creati se il cutoff è ancora futuro. Dopo la materializzazione ricalcola cutoff e lock dei turni già esistenti (rinvii / variazioni orario, EP06-07) senza sbloccare azioni già consumate.

## Metriche

- `fantasy_turn_generated_total` (`success` / `skipped` / `duplicate_window` / `upgraded`)
- `fantasy_turn_ensure_total`
- `fantasy_turn_opened_total`
- `fantasy_turn_fixture_excluded_total`
- `fantasy_turn_cutoff_recalculated_total`

## Rischi residui

- Numerazione turni indipendente dal calendario H2H (allineamento futuro).
- Timezone lega non ancora modellata: default `Europe/Rome`.
- Leghe non ancora `active` non ricevono turni automatici (serve attivazione o sync manuale).
- Il latch usa lo snapshot `observed_kickoff_at` (impostato in generazione). Un ricalcolo **prima** del fischio adotta il nuovo orario; uno **dopo** aggancia il lock e non riapre la finestra. Tra sync provider e job/`GET` il cutoff persistito può restare stantio per pochi minuti.
