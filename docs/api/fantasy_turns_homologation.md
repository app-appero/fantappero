# Omologazione turno e correzioni — EP07-07

| Metadato | Valore |
| --- | --- |
| Card | EP07-07 |
| Modulo | `backend/src/fantasy_turns/homologation.py` + `fantasy_turns/homologation_service.py` |
| Dipendenze | EP07-01/02/03 (fantavoto), EP07-04 (formazione effettiva), EP07-05 (risultato H2H), EP07-06 (classifica) |
| Requisiti | FR-OMO-01 |

## Ruolo

Chiude il ciclo di vita del turno: pubblica il risultato provvisorio (già
prodotto da EP07-01→06), lo rende **immutabile** una volta omologato, e
consente una **riapertura esplicita e auditata** (correzione) quando il
provider rettifica i dati ufficiali dopo l'omologazione.

## Stati (FR-OMO-01)

`FantasyRound.homologation_status`: `provisional` → `homologated` →
(correzione) → `provisional` → …

| Transizione | Funzione | Precondizione |
| --- | --- | --- |
| `provisional` → `homologated` | `homologate_round` | Tutte le fixture sono terminali (`FT`/`AET`/`PEN`) e hanno statistiche giocatore per entrambe le squadre reali |
| `homologated` → `provisional` | `apply_round_correction` | Motivo obbligatorio (non vuoto) |

Entrambe le transizioni sono una **UPDATE condizionale** sullo stato
corrente (`WHERE homologation_status = 'expected'`), non un semplice
"set": sotto concorrenza, un solo chiamante vede `rowcount == 1` e applica
la transizione; gli altri ricevono un errore esplicito
(`round_already_homologated` / `round_not_homologated`) invece di
sovrascriversi a vicenda o duplicare l'evento di audit. Verificato con un
test a due thread/connessioni reali contro lock di riga Postgres.

## Guardia sulla pipeline

Un turno omologato **non cambia più per nuove versioni della formula**.
La guardia è iniettata nei tre punti di ricalcolo esistenti, senza
modificarne la firma pubblica:

| Entrypoint | Guardia | Ambito |
| --- | --- | --- |
| `fantasy_ratings.service.compute_fixture_ratings` | `assert_fixture_not_homologated` | Per `fixture_id`, **in qualunque lega** la fixture sia stata omologata (una fixture del provider può appartenere a turni di leghe diverse) |
| `fantasy_lineups.substitution_service.compute_round_effective_lineups` | `assert_round_not_homologated` | Per `round_id` |
| `leagues.scoring_service.compute_round_results` | `assert_round_not_homologated` | Per `round_id` |

Ogni chiamata bloccata solleva `ValidationAuthError(code="round_homologated")`.
Il calcolo classifica (EP07-06, `compute_league_standings`) non è guardato
direttamente: legge solo risultati già persistiti (`result_final`) e non
ricalcola dati del turno.

## Correzione (FR-OMO-01 §Eccezioni)

`apply_round_correction` **non ricalcola nulla da sola**: riporta il turno
a `provisional` in modo atomico e auditato (motivo obbligatorio in
`ApplyRoundCorrectionRequest.reason`), così le chiamate successive a
`compute_fixture_ratings` / `compute_round_effective_lineups` /
`compute_round_results` tornano ammesse. Il turno resta `provisional`
finché un nuovo `homologate_round` non lo richiude esplicitamente.

## Entità

`fantasy_rounds` (estesa, EP06-01 + EP07-07): `homologation_status`
(enum `provisional`/`homologated`, default `provisional`),
`homologated_at`, `homologated_by_user_id` (FK `users`, `SET NULL`),
`homologation_formula_version`.

`league_audit_events`: due nuove azioni,
`fantasy_round_homologated` e `fantasy_round_correction_applied`
(quest'ultima con `details.reason`, `previousHomologatedAt`,
`previousFormulaVersion`).

L'omologazione ordinaria conserva l'admin in `actor_id`; quella eseguita dalla
pipeline automatica usa `actor_id = NULL` e
`details.source = automatic_live_pipeline`, senza attribuire l'azione a una
persona che non l'ha eseguita.

## API (permesso `global:operate`)

| Metodo | Path | Descrizione |
| --- | --- | --- |
| `POST` | `/fantasy-scoring/rounds/{roundId}/omologa` | Omologa il turno; richiede tutte le partite terminate |
| `POST` | `/fantasy-scoring/rounds/{roundId}/correzione` | Riapre un turno omologato (motivo obbligatorio nel body) |

Risposta (entrambi gli endpoint):

```json
{
  "roundId": "…",
  "homologationStatus": "homologated",
  "homologatedAt": "2026-08-17T21:00:00Z",
  "formulaVersion": "beta-v0.1"
}
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example --profile test up -d postgres-test

docker compose --env-file infra/local/.env.example run --rm api sh -lc \
  'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/fantasy_turns/test_homologation.py tests/integration/leagues/test_scoring_service.py -ra'
```

Test di integrazione sul corpus reale `39/1035055` (West Ham 3-1 Chelsea):
omologazione bloccata finché la fixture non è `FT`; una volta omologato,
tutti e tre gli entrypoint di ricalcolo sono bloccati; doppia omologazione
esplicitamente rifiutata; correzione con motivo vuoto rifiutata; correzione
valida riapre il turno, il ricalcolo torna ammesso, la ri-omologazione
produce un secondo evento di audit distinto. Test di concorrenza a due
thread/connessioni reali: un solo chiamante omologa, l'altro riceve
`round_already_homologated`, un solo evento di audit persistito.

## Relazioni

- Voto statistico: [`fantasy_ratings.md`](./fantasy_ratings.md)
- Formazione effettiva: [`fantasy_lineups_effective.md`](./fantasy_lineups_effective.md)
- Punteggio e scontro diretto: [`league_scoring.md`](./league_scoring.md)
- Classifica: [`league_standings.md`](./league_standings.md)
