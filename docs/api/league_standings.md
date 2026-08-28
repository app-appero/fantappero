# Classifica e criteri di parità — EP07-06

| Metadato | Valore |
| --- | --- |
| Card | EP07-06 |
| Modulo | `backend/src/leagues/standings.py` + `leagues/standings_service.py` |
| Dipendenze | EP07-05 (risultato scontro diretto) |
| Requisiti | FR-CLS-01 |

## Ruolo

Aggrega gli esiti finali degli scontri diretti (`league_calendar_slots`,
EP07-05) in una **classifica per lega**, sempre ricalcolata dall'origine.

## Regole (FR-CLS-01)

- Considera solo gli slot **non bye** con `result_final = true` e un
  `outcome` calcolato. Uno scontro non ancora finale (in attesa, non
  giocato) non aggiorna i due partecipanti: la squadra mostra semplicemente
  meno partite giocate delle altre.
- Il ricalcolo **ricostruisce da zero** il tabellino di ogni squadra dai
  risultati correnti invece di sommarne l'ultimo contributo: un ricalcolo
  non può mai duplicare una partita o un punto.
- **Decisioni Beta** (FR-CLS-01 §Eccezioni, aperte nei requisiti):
  - punteggio 3 (vittoria) / 1 (pareggio) / 0 (sconfitta), lo standard
    calcistico;
  - criteri di parità: punti → differenza reti fantasy → gol fantasy fatti →
    nome squadra (spareggio finale stabile e deterministico).

## Entità

`league_standings`: unique `(league_id, fantasy_team_id)`; `played`, `won`,
`drawn`, `lost`, `fantasy_goals_for`, `fantasy_goals_against`,
`fantasy_points_for`, `fantasy_points_against`, `points`, `position`,
`computed_at`. Include tutte le squadre della lega, anche con zero partite
giocate.

### Tre grandezze da non confondere (EP13-P02)

| Colonna UI | Campi | Significato |
| --- | --- | --- |
| **Pt** | `points` | Punti di classifica: 3 vittoria / 1 pareggio / 0 sconfitta |
| **GF:GS** | `fantasyGoalsFor` / `fantasyGoalsAgainst` | Gol fantasy fatti e subiti, cioè i risultati degli scontri |
| **FP:FS** | `fantasyPointsFor` / `fantasyPointsAgainst` | Fantapunti: somma dei Punti di formazione fatti e subiti, con un decimale |

`fantasy_points_*` è stato aggiunto da una migrazione **additiva**
(`b4d7e2f9c118`) con default `0`: nessun dato è stato cancellato e i valori
reali compaiono al primo ricalcolo, che riparte sempre dagli slot di
calendario. Le righe calcolate prima di EP13-P02, o gli slot storici privi di
`home_score`/`away_score`, restano coerenti con `0`.

**I criteri di parità non sono cambiati**: i Fantapunti sono informativi e non
entrano nell'ordinamento, che resta punti → differenza reti fantasy → gol
fantasy fatti → nome squadra. Usarli come spareggio sarebbe una decisione di
prodotto ancora da prendere.

Vedi il glossario Punti / Gol fantasy in
[`league_scoring.md`](./league_scoring.md).

## API

| Metodo | Path | Permesso | Descrizione |
| --- | --- | --- | --- |
| `POST` | `/fantasy-scoring/leagues/{leagueId}/classifica` | `global:operate` | Ricalcola la classifica dagli scontri diretti finali |
| `GET` | `/leagues/{leagueId}/classifica` | `league:view` (membro) | Classifica persistita, ordinata per posizione |

## Verifica

```bash
docker compose --env-file infra/local/.env.example --profile test up -d postgres-test

docker compose --env-file infra/local/.env.example run --rm api sh -lc \
  'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/leagues/test_standings.py tests/integration/leagues/test_scoring_service.py -ra'
```

Test di integrazione: prosegue lo scenario reale West Ham–Chelsea (EP07-05)
fino alla classifica — punti, gol fantasy fatti/subiti ricostruibili dal
risultato dello scontro diretto; ricalcolo stabile (nessun accumulo).

## Relazioni

- Punteggio e scontro diretto: [`league_scoring.md`](./league_scoring.md)
- Formazione effettiva: [`fantasy_lineups_effective.md`](./fantasy_lineups_effective.md)

## Aggiornamento

`compute_round_results` (EP07-05) richiama automaticamente
`compute_league_standings` dopo aver persistito gli esiti H2H: la classifica
segue il flusso naturale dei risultati senza un secondo passo manuale.
Il `POST /fantasy-scoring/leagues/{leagueId}/classifica` resta disponibile
per ricalcoli espliciti (operatore).

`GET /leagues/{leagueId}/classifica` include `teamName` per la UI.
