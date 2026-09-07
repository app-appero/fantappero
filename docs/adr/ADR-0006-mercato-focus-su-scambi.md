# ADR-0006 — Mercato: tab "Scambi", Svincolati e Svincolo volontario nascosti

| Metadato | Valore |
| --- | --- |
| Stato | Accettato |
| Data | 2026-09-07 |
| Card | — (decisione di prodotto post-EP08, non legata a una card specifica) |
| Dipendenza | EP08-01 (sessione mercato sigillata), EP08-03 (svincoli), EP08-04 (svincolo volontario), EP08-05/06/07 (scambi), EP08-08 (storico mercato), EP05-06 (storico rosa / ownership intervals) |
| Relazioni | `apps/web/src/pages/MarketHubPage.tsx`; `apps/web/src/pages/MarketPage.tsx`; `apps/web/src/pages/WaiverPage.tsx`; `apps/web/src/pages/RosterPage.tsx`; `backend/src/market/*`; `backend/src/fantasy_teams/service.py` |

## Contesto

La tab "Mercato" nell'hub (`/mercato`, dentro `MarketHubPage.tsx`) conteneva già una
pagina **chiamata anch'essa "Mercato"** (`MarketPage.tsx`), che raccoglieva tre cose
diverse — svincolo volontario, proposta/gestione scambi, storico — mentre la tab
sorella "Svincolati" (`WaiverPage.tsx`) offriva un quarto meccanismo, la **sessione
svincolati a buste chiuse** (EP08-03). Risultato: "mercato dentro mercato" e quattro
modi diversi di muovere un giocatore, poco distinguibili per un utente.

Verificando il codice, tre di questi meccanismi sono risultati ridondanti rispetto a
un flusso che esiste già altrove:

1. **Svincolati (sessione a buste chiuse, EP08-03)** — richiede sempre di dichiarare
   un giocatore da tagliare per ogni offerta (`release_athlete_id` obbligatorio),
   proprio perché una squadra non può restare con uno slot vuoto. Ma lo stesso
   risultato (esci un giocatore, entra un altro, subito, senza slot vuoti) si ottiene
   già in **Rosa**, senza dover aspettare l'apertura/chiusura di una finestra e senza
   il rischio di parità/spareggio.
2. **Svincolo volontario (EP08-04)** — libera uno slot con un rimborso **parziale**
   (`market/service.py::apply_release`, regola in `LeagueRules`: default 50% per
   svincolo volontario, 100% per uscita dai cinque campionati). Ma in **Rosa**
   (`fantasy_teams/service.py::release_slot`/`assign_slot`, endpoint
   `/amministrazione/squadre/{team}/slot/{index}`, disponibile al proprietario della
   squadra oltre che all'admin) lo stesso slot si libera e si riassegna con un
   rimborso **sempre pieno** — due regole economiche diverse per lo stesso bisogno.
3. **Storico mercato (EP08-08)** — legge il log di audit e mostra acquisti/svincoli/
   scambi/interventi. Ma **Rosa ha già un proprio storico** (`GET /rosa/storico`,
   basato su `RosterOwnershipInterval`: chi è entrato/uscito da ogni slot, quando, a
   quanti crediti), popolato dagli stessi punti di scrittura — **anche gli scambi
   eseguiti** lo alimentano (`market/trade_execution.py` chiama
   `sync_ownership_on_assign`/`sync_ownership_on_release`, le stesse funzioni usate
   da Rosa e dal mercato svincolati/asta).

## Decisione

1. **Tab "Svincolati" nascosta.** In `MarketHubPage.tsx`, `SHOW_WAIVER_TAB = false`
   toglie il pulsante dalla `TabList`. Route (`/svincoli`), `TabPanel`, `WaiverPage.tsx`
   e tutto il backend (`market/live_*` no — quello è l'asta a rilanci, invariata;
   qui parliamo di `market/models.py::MarketSession(kind=WAIVER)`,
   `market/service.py`, `market/router.py` sezione `mercato/svincoli/*`) restano
   intatti e raggiungibili via URL diretto.
2. **Tab "Mercato" → "Scambi".** Stessa route (`/mercato`), stesso componente
   (`MarketPage.tsx`), ma rinominata (label della tab, titolo pagina, breadcrumb) e
   **limitata alla proposta/gestione degli scambi tra squadre** (EP08-05/06/07):
   creazione proposta, lista proposte con accetta/rifiuta/controproponi, approvazione
   admin dove richiesta.
3. **Sezione "Svincolo volontario" nascosta.** In `MarketPage.tsx`,
   `SHOW_VOLUNTARY_RELEASE = false`. Stato, handler e chiamate API
   (`previewVoluntaryRelease`/`applyVoluntaryRelease`) restano nel codice.
4. **Sezione "Storico mercato" nascosta.** Stesso file, `SHOW_MARKET_HISTORY = false`.
   L'hook `useMarketHistory` e l'endpoint `GET /mercato/storico` restano nel codice.
5. **Invariante confermato: una rosa non può avere slot vuoti "in sospeso".** Il
   percorso supportato per sostituire un giocatore è **Rosa**: si rilascia il
   giocatore uscente (rimborso pieno) e si assegna subito un giocatore libero dal
   listone (tutti i calciatori non presenti in `ownership` sono per definizione
   svincolati) — nella stessa schermata, senza passare da una finestra di mercato.

Sia il codice frontend che i test relativi alle sezioni nascoste sono stati
**mantenuti, non cancellati** (`MarketPage.real.test.tsx`, i due `describe` di
"svincolo volontario" e "storico" sono marcati `describe.skip` con un commento che
rimanda a questo ADR).

### Come riattivare

Riportare a `true` il flag interessato (`SHOW_WAIVER_TAB` in `MarketHubPage.tsx`;
`SHOW_VOLUNTARY_RELEASE`/`SHOW_MARKET_HISTORY` in `MarketPage.tsx`) e rimuovere il
corrispondente `.skip` nei test. Nessuna migrazione, route o modifica backend è
necessaria: non è stato toccato nulla lato server.

## Conseguenze

**Positive.** Un solo percorso per "cambio giocatore" (Rosa), sempre disponibile,
senza attese di finestre né spareggi. La tab "Scambi" ha uno scopo solo. Sparisce la
duplicazione "mercato dentro mercato" e la sovrapposizione tra quattro meccanismi
diversi con la stessa finalità.

**Negative.**
- La penale economica del 50% sullo svincolo volontario **esce dal prodotto**
  finché il flag non viene riattivato: oggi l'unico modo di liberare uno slot
  (Rosa) rimborsa sempre il 100%. Se in futuro serve di nuovo un disincentivo
  economico allo svincolo, va reintrodotto esplicitamente.
- Il rimborso pieno via Rosa non registra un "motivo" (non distingue uno svincolo
  volontario da un'uscita dai cinque campionati): la distinzione, se servirà ancora,
  andrà ridisegnata.
- Lo storico rosa (`/rosa/storico`) mostra gli intervalli di possesso **della
  singola squadra** (chi è entrato/uscito, quando, a quanti crediti) ma non la
  visione unificata "squadra A ↔ squadra B" che aveva lo Storico mercato per gli
  scambi: chi vuole ricostruire uno scambio deve guardare lo storico di entrambe le
  squadre coinvolte.
- La sessione svincolati sigillata (offerte nascoste, spareggio automatico a
  parità) smette di essere usabile da UI, pur restando pronta nel codice.

**Rischio accettato.** Nessuna delle due strade rimaste (Rosa, Scambi) applica oggi
una penale o un vincolo temporale ai movimenti di rosa: chi vuole disincentivare i
cambi frequenti dovrà introdurre una nuova regola, non riesumarne una vecchia
1:1 — le due implementazioni nascoste (svincolo volontario al 50%, mercato
svincolati a buste chiuse) restano un riferimento ma non sono la soluzione
già pronta per un vincolo pensato per Rosa.

## Alternative scartate

- **Cancellare del tutto codice, route e test** delle sezioni ritenute ridondanti:
  scartata, si perderebbe lavoro già testato e la possibilità di riattivarlo
  rapidamente se la valutazione cambia.
- **Spostare "Storico mercato" in una tab propria** invece di nasconderlo: scartata
  per ora — Rosa offre già una vista equivalente (per squadra) sugli stessi dati,
  alimentata dagli stessi punti di scrittura, incluse le esecuzioni di scambio.
