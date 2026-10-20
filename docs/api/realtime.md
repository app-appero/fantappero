# Tempo reale (SSE) — EP09-07

`GET /realtime/stream?leagueIds=<id>,<id>` — `text/event-stream`, auth Bearer come il resto dell'API.
Eventi e tipi in `packages/contracts/src/realtime.ts`.

| Evento | Canale | Quando | Usato da |
| --- | --- | --- | --- |
| `notification.created` | personale | A ogni notifica creata (dopo il commit, anche da job) | Campanella/badge web e mobile |
| `market.updated` `kind: "trades"` | lega | Ogni modifica a `/leagues/{id}/mercato/scambi/...` | Elenco proposte di scambio |
| `market.updated` `kind: "auction_live"` (+ `sessionId`) | lega | Ogni modifica a `/mercato/asta-live/...` | Asta live: ricarica subito invece di aspettare il polling (2,5 s) |
| `market.updated` `kind: "market"` | lega | Altre modifiche al mercato (buste chiuse, rilasci, svincolati) | Disponibile per le schermate che vogliono ricaricare |

Gli eventi sono **segnali**: portano solo tipo e id, il client ricarica i dati con le sue chiamate e i suoi permessi. Il canale di lega è accessibile solo ai membri.

## Come funziona

- Backend: Redis pub/sub (`REDIS_URL`). Le notifiche pubblicano a commit avvenuto (`realtime/publisher.py`); il mercato passa da un middleware (`realtime/middleware.py`) che pubblica dopo ogni scrittura riuscita sotto `/mercato/`, senza hook per endpoint. Un `heartbeat` ogni 15 s tiene viva la connessione; il flusso si chiude ogni 10 minuti (il token scade) e il client si riconnette.
- Senza Redis: `503 realtime_unavailable`, nessun errore per l'utente.
- **Il polling resta** come ripiego (notifiche 20/30 s, asta live 2,5 s): il tempo reale lo anticipa, non lo sostituisce.
- Web: `fetch` in streaming (`EventSource` non manda l'header Authorization). Mobile: `expo/fetch`.

## Limiti noti

- Le buste chiuse risolte da job in background non passano dal middleware: l'utente le vede dalla notifica (`notification.created`), non da `market.updated`.
- Gli eventi non sono ripetuti a chi era disconnesso: alla riconnessione il client si affida ai dati ricaricati normalmente.
- FastAPI 0.116: le sessioni DB dei dependency con `yield` si chiudono prima dello streaming. Se si passa a >= 0.118 va riverificato che `/realtime/stream` non tenga aperta una connessione DB.
