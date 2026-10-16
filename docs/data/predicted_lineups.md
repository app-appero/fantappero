# Formazioni probabili (FotMob via RapidAPI)

Le formazioni previste arrivano da FotMob e restano separate dalle formazioni ufficiali già salvate da API-Football. Un JSON valido non basta per usarle in formazione: servono i controlli sotto.

## Variabili

| Variabile | Dove | Effetto |
|---|---|---|
| `RAPIDAPI_KEY` | API e worker Railway | Header `x-rapidapi-key`. Se manca, il job risponde senza chiamare il provider. |
| `FOTMOB_BASE_URL` | opzionale | Default `https://fotmob-api.p.rapidapi.com`. |
| `PREDICTED_LINEUPS_ENABLED` | job automatici | Default acceso. Il pannello operatore può spegnerlo. |
| `PREDICTED_LINEUPS_INTERVAL_SECONDS` | job automatici | Default 86400 (una volta al giorno). |
| `FOTMOB_MAX_LINEUP_CALLS` | tetto per giro | Default 40 formazioni, più una chiamata per data. |
| `PREDICTED_LINEUPS_MIN_AGE_HOURS` | cache | Default 20. Il pulsante manuale ignora questo limite. |

La chiave non va nel repository, nei log né nelle risposte HTTP. Su Railway va impostata sull'ambiente dell'API e del worker, poi si ridistribuisce.

## Endpoint

- Provider: `GET /api/v1/matches/by-date?date=YYYYMMDD` e `GET /api/v1/matches/{matchId}/lineups`.
- Interno, solo admin di lega: `POST /leagues/{leagueId}/turni/probabili-formazioni`.
- Lettura partita: `GET /leagues/{leagueId}/turni/{roundId}/partite/{fixtureId}` aggiunge `lineupKind`, `lineupNote` e `unavailablePlayers`. Se esiste la formazione ufficiale, quella resta; gli indisponibili si aggiungono lo stesso.
- Rosa formazione: `probableHint` (`starter` | `bench` | `unavailable`), `probableNote`, `selectionBlocked`.

## Dati

- `fotmob_fixture_links`: fixture interna ↔ match FotMob. Gli id non si mescolano con API-Football.
- `predicted_lineup_snapshots`: uno snapshot per lettura (`predicted` o `confirmed` solo se il provider lo dice). Non si sovrascrivono.
- `predicted_lineup_players`: titolari, panchina e indisponibili. `athlete_id` è nullo se il nome non è univoco nella rosa.

Affidabilità, da controlli misurabili e non da una percentuale:

- `validated`: entrambe le squadre hanno 11 titolari unici, modulo `N-N-N`, nessun titolare anche indisponibile, e ogni titolare è nella rosa.
- `partially_validated`: c'è almeno un titolare collegato alla rosa, ma manca uno dei controlli.
- `unverified`: struttura presente, zero giocatori collegati. Si mostra in partita e non blocca la formazione.
- `rejected`: vuota, oppure le squadre non corrispondono alla partita. Non si usa.

`selectionBlocked` vale solo se il giocatore è in rosa, l'assenza è `injury` o `suspension` (anche espulsione) e il testo non è incerto (`Doubtful`, `Back in training`, `A few weeks`). Una data di rientro già passata rispetto al calcio d'inizio non blocca.

## Job

Catalogo `sports-predicted-lineups`, task `sports_data.sync_predicted_lineups`. Prende le partite non iniziate dei turni europei nelle prossime 4 giorni. Il pulsante **Aggiorna probabili** nei turni europei fa lo stesso giro, solo per la lega, anche se lo snapshot è recente.

Il log `fotmob_predicted_lineups_synced` riporta i conteggi, mai la chiave.

## Limiti

- Senza `RAPIDAPI_KEY` non c'è alcun aggiornamento.
- Il tetto di chiamate può lasciare fuori partite più lontane nello stesso giro.
- Una formazione `predicted` non è una conferma sportiva. Ligue 1 non è stata verificata su chiamate reali in questo ambiente.
- Il motore di voto e le formazioni IA non usano questi dati: cambierebbero i risultati senza un backtest.
