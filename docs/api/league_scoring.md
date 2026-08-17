# Punteggio squadra e scontro diretto — EP07-05

| Metadato | Valore |
| --- | --- |
| Card | EP07-05 |
| Modulo | `backend/src/leagues/scoring.py` + `leagues/scoring_service.py` |
| Dipendenze | EP07-04 (formazione effettiva), EP07-01/02/03 (fantavoto), EP03-06 (calendario H2H) |
| Requisiti | FR-SCO-03 |

## Ruolo

Converte i fantavoti degli **undici effettivi** (`effective_lineups`, EP07-04)
nel **risultato provvisorio** dello scontro diretto e lo persiste sullo slot
di calendario (`league_calendar_slots`, EP03-06).

## Algoritmo (FR-SCO-03)

1. Somma `player_match_ratings.fantasy_score` dei calciatori in
   `effective_lineups.effective_starter_ids` per ciascuna squadra (un
   calciatore senza voto contribuisce 0, in modo deterministico).
2. Converte il totale in **gol fantasy**:

   | Punti | Gol fantasy |
   | --- | --- |
   | ≤ 65,5 | 0 |
   | 66 – 71,5 | 1 |
   | 72 – 77,5 | 2 |
   | +6 punti | +1 gol |

3. Confronta i gol fantasy delle due squadre: più gol vince, pari gol pareggio.
4. Il risultato è **`resultFinal = true`** solo se tutte le fixture del turno
   sono in stato terminale (`FT`/`AET`/`PEN`); altrimenti resta provvisorio
   pur avendo un punteggio calcolato (FR-SCO-03: "distingue componenti
   definitive e ancora in attesa").
5. **Decisione aperta** (FR-SCO-03 §Eccezioni): scarto minimo tra squadre
   nella stessa fascia gol. Default Beta — l'esito si basa solo sui gol
   fantasy, non sul punteggio grezzo: stessa fascia ⇒ pareggio.

Precondizione: la formazione effettiva (EP07-04) deve già essere calcolata
per entrambe le squadre; in caso contrario lo scontro è saltato (`skipped`)
e non produce un risultato parziale o errato.

## Entità

`league_calendar_slots` (estesa, EP03-06 + EP07-05): `home_score`,
`away_score`, `home_fantasy_goals`, `away_fantasy_goals`,
`outcome` (`home`/`away`/`draw`), `result_final`, `result_computed_at`.

Il turno fantasy `(league_id, round_number)` si abbina allo slot di
calendario tramite `FantasyRound.number == LeagueCalendarSlot.round_number`
sulla stessa lega; i lati home/away si risolvono da
`LeagueMembership` → `FantasyTeam.membership_id`.

## API (permesso `global:operate`)

| Metodo | Path | Descrizione |
| --- | --- | --- |
| `POST` | `/fantasy-scoring/rounds/{roundId}/risultati` | Calcola e persiste i risultati di tutti gli scontri diretti del turno |
| `GET` | `/fantasy-scoring/rounds/{roundId}/risultati` | Risultati persistiti (uno per scontro diretto, esclusi i bye) |

Risposta compute:

```json
{
  "roundId": "…",
  "resultFinal": true,
  "matchups": 4,
  "created": 4,
  "updated": 0,
  "unchanged": 0,
  "skipped": 0
}
```

## Verifica

```bash
docker compose --env-file infra/local/.env.example --profile test up -d postgres-test

docker compose --env-file infra/local/.env.example run --rm api sh -lc \
  'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/leagues/test_scoring.py tests/integration/leagues/test_scoring_service.py -ra'
```

Test di integrazione sul corpus reale `39/1035055` (West Ham 3-1 Chelsea):
West Ham (modulo 4-5-1, una sostituzione automatica) contro Chelsea (modulo
3-4-3, undici titolari tutti con voto, nessuna sostituzione) — risultato
`resultFinal = true` (fixture `FT`), gol fantasy ricostruibili dai punteggi
persistiti, ricalcolo stabile.

## Relazioni

- Formazione effettiva: [`fantasy_lineups_effective.md`](./fantasy_lineups_effective.md)
- Voto statistico e fantavoto: [`fantasy_ratings.md`](./fantasy_ratings.md)
