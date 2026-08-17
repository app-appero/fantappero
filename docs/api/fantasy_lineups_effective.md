# Formazione effettiva e sostituzioni automatiche — EP07-04

| Metadato | Valore |
| --- | --- |
| Card | EP07-04 |
| Modulo | `backend/src/fantasy_lineups/substitution_service.py` + `fantasy_lineups/rules.py` |
| Dipendenze | EP07-02 (eleggibilità voto), EP06-02/EP06-04 (formazione salvata, panchina ordinata) |
| Requisiti | FR-SUB-01 |

## Ruolo

Risolve, per ogni squadra fantasy di un turno, quali titolari sono rimasti
**senza voto** (EP07-02, `player_match_ratings.eligible = false`) e applica le
sostituzioni automatiche descritte da FR-SUB-01, producendo la **formazione
effettiva** persistita in `effective_lineups`.

Il motore puro (`fantasy_lineups/rules.py::resolve_automatic_substitutions`)
era già stato introdotto in EP06-04 come preview; EP07-04 lo collega ai voti
reali e ne persiste il risultato per turno, in modo deterministico e
ricalcolabile.

## Algoritmo (FR-SUB-01)

1. Si individuano i titolari **senza voto**: nessuna riga `player_match_ratings`
   eleggibile per quel calciatore sulle fixture del turno.
2. Si scorre la panchina **nell'ordine salvato** (`lineup_players.sort_order`).
3. Il primo panchinaro **con voto valido** e **dello stesso ruolo** del titolare
   senza voto entra al suo posto.
4. Si applicano al massimo `league_rules.max_automatic_substitutions` cambi
   (standard 5, configurabile 0–5 per lega). Oltre il limite, i panchinari
   restanti sono saltati con motivo `limit_reached`.
5. Un titolare con **qualsiasi voto valido** (anche basso) non viene mai
   sostituito. Senza sostituto compatibile, la squadra gioca con quel titolare
   ancora in formazione (nessun 6 automatico: quello è EP07-07/FR-RIN-01).
6. Ogni panchinaro non utilizzato è spiegato con un motivo:
   `not_eligible` (senza voto), `role_unresolved`, `no_compatible_starter`
   (nessun titolare del suo ruolo è senza voto) o `limit_reached`.

Il conteggio di ruolo dell'XI effettivo (`moduleValid`) riflette il modulo
salvato: le sostituzioni sono sempre a parità di ruolo, quindi resta valido
anche quando un titolare senza voto non trova sostituto.

## Entità

| Tabella | Vincoli | Note |
| --- | --- | --- |
| `effective_lineups` | unique `(round_id, fantasy_team_id)` | Upsert idempotente: un ricalcolo sovrascrive la riga, non la duplica |

Colonne: `module`, `module_valid`, `max_automatic_substitutions` (snapshot del
limite usato), `effective_starter_ids` (JSONB), `substitutions_json` (`outAthleteId`,
`inAthleteId`, `role`, `order`), `skipped_json` (`athleteId`, `role`, `reason`),
`computed_at`.

## Regolamento di lega

`league_rules.max_automatic_substitutions` (Integer, default 5, vincolo
`BETWEEN 0 AND 5`), configurabile da `PUT /leagues/{id}/amministrazione/regolamento`
come `minutesThreshold` (EP07-02). Un override esplicito è accettato anche in
compute (vedi sotto), sempre validato nello stesso intervallo.

## API (permesso `global:operate`)

| Metodo | Path | Descrizione |
| --- | --- | --- |
| `POST` | `/fantasy-lineups/rounds/{roundId}/formazione-effettiva` | Calcola e persiste la formazione effettiva di tutte le squadre del turno |
| `GET` | `/fantasy-lineups/rounds/{roundId}/formazione-effettiva/{fantasyTeamId}` | Formazione effettiva persistita per una squadra |

Body compute (opzionale):

```json
{ "maxAutomaticSubstitutions": 3 }
```

Risposta compute:

```json
{
  "roundId": "…",
  "maxAutomaticSubstitutions": 5,
  "teams": 8,
  "created": 8,
  "updated": 0,
  "unchanged": 0
}
```

Risposta GET:

```json
{
  "id": "…",
  "roundId": "…",
  "fantasyTeamId": "…",
  "submissionId": "…",
  "module": "4-5-1",
  "moduleValid": true,
  "maxAutomaticSubstitutions": 5,
  "effectiveStarterIds": ["…"],
  "substitutions": [
    { "outAthleteId": "…", "inAthleteId": "…", "role": "C", "order": 1 }
  ],
  "skipped": [
    { "athleteId": "…", "role": "C", "reason": "not_eligible" },
    { "athleteId": "…", "role": "D", "reason": "no_compatible_starter" }
  ],
  "computedAt": "2026-08-17T…Z"
}
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example --profile test up -d postgres-test

docker compose --env-file infra/local/.env.example run --rm api sh -lc \
  'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/fantasy_lineups tests/integration/fantasy_lineups tests/integration/leagues -ra'
```

Test di integrazione dedicati sul corpus reale `39/1035055` (West Ham 3-1
Chelsea, modulo 4-5-1): un titolare senza voto (Fornals, sotto soglia senza
evento rilevante) viene sostituito dal primo panchinaro dello stesso ruolo con
voto valido; un panchinaro senza voto e uno con voto ma ruolo non richiesto
restano spiegati in `skipped`.

## Relazioni

- Voto statistico e bonus/malus: [`fantasy_ratings.md`](./fantasy_ratings.md)
- Formazione, moduli, panchina, mosse tattiche: [`fantasy_lineups.md`](./fantasy_lineups.md)
