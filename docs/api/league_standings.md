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
`drawn`, `lost`, `fantasy_goals_for`, `fantasy_goals_against`, `points`,
`position`, `computed_at`. Include tutte le squadre della lega, anche con
zero partite giocate.

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
