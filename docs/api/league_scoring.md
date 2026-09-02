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
   sono in stato terminale (`FT`/`AET`/`PEN`), le statistiche giocatore sono
   disponibili per entrambe le squadre reali di ogni fixture e tutte le
   formazioni effettive dei due lati sono risolte. Altrimenti resta provvisorio
   pur avendo un punteggio calcolato (FR-SCO-03: "distingue componenti
   definitive e ancora in attesa").
5. **Decisione aperta** (FR-SCO-03 §Eccezioni): scarto minimo tra squadre
   nella stessa fascia gol. Default Beta — l'esito si basa solo sui gol
   fantasy, non sul punteggio grezzo: stessa fascia ⇒ pareggio.

Precondizione: la formazione effettiva (EP07-04) deve già essere calcolata
per entrambe le squadre; in caso contrario lo scontro è saltato (`skipped`)
e non produce un risultato parziale o errato.

## Pipeline automatica e LIVE

I job centralizzati provider `LIVE` (60 s di base) e `POST_MATCH` (10 min)
acquisiscono eventi e snapshot giocatore una sola volta per fixture. Nella
stessa transazione `fantasy_turns.live_pipeline` riusa i service esistenti in
quest'ordine: voto di lega → sostituzioni → risultato H2H → classifica →
omologazione. Non esistono chiamate provider per giocatore dai browser.

Durante il live i rating sono isolati per `league_id`, così la soglia minuti
della lega non può sovrascrivere quella di un'altra lega sulla stessa fixture.
La classifica viene sempre ricostruita dai soli slot `result_final=true`: un
poll ripetuto sovrascrive lo stesso slot e non incrementa due volte giocate,
punti o gol.

`GET /leagues/{leagueId}/calendario/h2h` marca uno scontro `live=true` solo
quando una fixture in corso coinvolge davvero un suo titolare, tramite ID
atleta/provider e coppia stagione-club. Fra una partita reale e la successiva
lo stato è **Provvisorio / in attesa**, non un falso LIVE. Il dettaglio espone
per ogni giocatore squadra reale, stato fixture, voto base, bonus, malus,
componenti e totale; web e mobile effettuano polling adattivo verso il backend.

## Glossario delle due grandezze (EP13-P02)

Lo scontro diretto produce **due** numeri distinti, che la UI deve nominare
entrambi invece di mostrarne uno tra parentesi:

| Nome UI | Campi API | Che cos'è |
| --- | --- | --- |
| **Punti** | `homeScore` / `awayScore` | Somma dei fantavoti degli undici effettivi, con un decimale (es. `72,5`) |
| **Gol fantasy** | `homeFantasyGoals` / `awayFantasyGoals` | I Punti convertiti in gol con le soglie qui sopra: è il risultato dello scontro (es. `2 – 1`) |

Due squadre nella stessa fascia hanno Punti diversi ma **stessi Gol fantasy**,
quindi pareggiano: mostrare solo i Gol fantasy nasconde questa informazione,
mostrare solo i Punti non spiega l'esito.

Formattazione condivisa in `packages/contracts/src/h2hScore.ts`
(`describeH2HResult`): locale `it-IT` con la virgola decimale, e un valore non
calcolato resta `—` — **non viene mai reso come `0`**. La conversione Punti →
Gol fantasy resta di competenza del backend e non va replicata nei client.

In classifica gli aggregati corrispondenti sono `fantasyGoalsFor/Against`
(**GF:GS**) e `fantasyPointsFor/Against` (**FP:FS**, i Fantapunti), entrambi
distinti da `points`, che sono i punti di classifica 3/1/0. Vedi
[`league_standings.md`](./league_standings.md).

## Entità

`league_calendar_slots` (estesa, EP03-06 + EP07-05): `home_score`,
`away_score`, `home_fantasy_goals`, `away_fantasy_goals`,
`outcome` (`home`/`away`/`draw`), `result_final`, `result_computed_at`.

Il turno fantasy si abbina alle giornate H2H tramite la mappatura esplicita
per finestra temporale introdotta da EP13-P03
(`league_calendar_round_windows`, risoluzione in
`leagues/calendar_round_mapping.py`); sui calendari generati prima resta il
criterio `FantasyRound.number == LeagueCalendarSlot.round_number` sulla stessa
lega. I lati home/away si risolvono da `LeagueMembership` →
`FantasyTeam.membership_id`.

## API

| Metodo | Path | Permesso | Descrizione |
| --- | --- | --- | --- |
| `POST` | `/fantasy-scoring/rounds/{roundId}/risultati` | `global:operate` | Calcola e persiste i risultati di tutti gli scontri diretti del turno |
| `GET` | `/fantasy-scoring/rounds/{roundId}/risultati` | `global:operate` **oppure** `matchday:view` (membro della lega del turno) | Risultati persistiti (uno per scontro diretto, esclusi i bye) |
| `GET` | `/leagues/{leagueId}/calendario/h2h` | `matchday:view` | Aggregato giornate H2H + score (UI `/turni`) |
| `GET` | `/leagues/{leagueId}/calendario/scontri/{slotId}` | `matchday:view` | Dettaglio scontro con formazioni e fantavoti |

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
- Omologazione e correzioni: [`fantasy_turns_homologation.md`](./fantasy_turns_homologation.md)
