# EP12-02 — Test proprietà e concorrenza

| Metadato | Valore |
| --- | --- |
| Card | EP12-02 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | Tutte le Epic Must (M1–M4) |
| Stima originale | 3–5 giorni |

## Stato implementazione (branch `claude/M5`)

**Parzialmente implementata.** Durante l'implementazione è emerso che la ricognizione
iniziale sottostimava la copertura già esistente: il repo aveva già test di concorrenza
con `ThreadPoolExecutor` per ledger crediti, ownership rosa, risoluzione asta, rilascio/
refund, proposte di scambio, decisione scambio, bid d'asta, inviti nominali e omologazione
turni (12 file con pattern di concorrenza già verificato via `grep`). Il gap reale era più
stretto di quanto documentato sotto:

- **Aggiunto**: test di concorrenza per il salvataggio formazione (`fantasy_lineups`,
  unico dominio senza copertura), in
  `backend/tests/integration/fantasy_lineups/test_fantasy_lineups.py::test_concurrent_identical_lineup_saves_produce_single_revision`.
- **Aggiunto**: `hypothesis` come dipendenza dev (`backend/pyproject.toml`) e property
  test in `backend/tests/property/test_ledger_properties.py` — invarianti pure sui
  validator (`validate_ledger_balance_non_negative`, `validate_credit_amount_nonzero`) più
  un property test contro Postgres reale su `apply_ledger_movement`/`reconstruct_balance`
  con sequenze casuali di movimenti (saldo mai negativo, sempre ricostruibile).
- **Non implementato in questa sessione** (priorità più bassa, valutare in un passaggio
  successivo se necessario): concorrenza dedicata per `market/test_waiver_session.py`
  (probabile copertura indiretta già garantita dalla stessa logica di risoluzione
  condivisa con l'asta, testata in `test_auction_resolution.py`) e per
  `market/test_trade_admin_approval.py`.
- Verificato via Docker Compose (`postgres-test` + `redis`, immagine `api` rebuildata):
  `pytest tests/integration/fantasy_lineups` (13 passed) e `pytest tests/property`
  (4 passed), oltre a `ruff check`/`ruff format --check` sui file toccati.

## Obiettivo e scope

Stressare ledger crediti, buste d'asta, scambi, formazione e ricalcolo per garantire
**nessun saldo negativo, doppia assegnazione o risultato non deterministico**, con piano,
dati di test, responsabile ed evidenze definiti.

## Stato attuale nel repo (gap)

- Esistono solo test unit/integration "a scenario singolo" in
  `backend/tests/unit/{market,fantasy_teams,fantasy_lineups,fantasy_turns}` e
  `backend/tests/integration/{market,fantasy_teams,fantasy_lineups,fantasy_turns}`.
  Nessun property-based test (generazione automatica di input/sequenze) e nessun test di
  concorrenza reale (più worker/connessioni che operano in parallelo sullo stesso stato).
- Il pattern di locking del dominio è già solido e riusabile come base da testare:
  **lock pessimistico a livello riga via `SELECT ... FOR UPDATE`** (SQLAlchemy
  `.with_for_update()`), usato in:
  - `backend/src/fantasy_teams/ledger.py` — ledger crediti
  - `backend/src/fantasy_teams/ownership.py`, `service.py` — ownership/composizione rosa
  - `backend/src/market/service.py`, `assignment.py`, `trade_service.py`,
    `trade_execution.py` — buste, assegnazioni, proposte di scambio
  - `backend/src/fantasy_lineups/service.py` — formazioni
  - `backend/src/fantasy_turns/service.py` — turni/omologazione
  - Nota: `backend/src/sports_data/scheduler/locks.py` usa lock Redis distribuito, ma è
    fuori scope qui (riguarda il polling dati sportivi, non ledger/mercato).
- `backend/pyproject.toml` non elenca `hypothesis` tra le dipendenze dev: da valutare se
  introdurla o se property test "manuali" (loop parametrizzati con `pytest.mark.parametrize`
  su sequenze generate) siano sufficienti per lo scope Beta.

## Piano d'azione

1. **Inventariare le invarianti di dominio da garantire** (una per modulo, con
   riferimento a funzione/servizio):
   - Ledger: il saldo crediti di una squadra non scende mai sotto lo zero indipendentemente
     dall'ordine di applicazione delle transazioni concorrenti (`ledger.py`).
   - Buste/asta: un giocatore non può essere assegnato a due squadre contemporaneamente;
     risoluzione di parità è deterministica anche con più richieste concorrenti
     (`assignment.py`, `service.py`).
   - Scambi: uno scambio non può essere eseguito due volte né lasciare un giocatore
     "duplicato" tra le due rose coinvolte (`trade_service.py`, `trade_execution.py`).
   - Formazioni: il salvataggio concorrente della stessa formazione da due richieste non
     produce stati incoerenti (es. panchina con lo stesso giocatore titolare)
     (`fantasy_lineups/service.py`).
   - Ricalcolo/omologazione turni: un ricalcolo concorrente con una nuova richiesta di
     omologazione non produce un doppio conteggio o un punteggio diverso a parità di
     input (`fantasy_turns/service.py`).
2. **Scrivere test di concorrenza mirati** per ciascuna invariante: eseguire N operazioni
   concorrenti (thread/processi o connessioni DB parallele contro `postgres-test`) che
   competono sulla stessa risorsa (stessa squadra, stesso giocatore, stessa formazione) e
   asserire che l'invariante regge sempre, ripetendo il test più volte per ridurre falsi
   negativi da timing.
3. **Aggiungere property test** sulle funzioni di calcolo pure e deterministiche (es.
   risoluzione parità buste, calcolo punteggio) generando input randomizzati entro i
   vincoli di dominio e verificando proprietà invarianti (es. "la somma dei crediti
   assegnati non supera mai il budget iniziale della lega").
4. **Isolare questi test in una sotto-cartella dedicata** (proposta:
   `backend/tests/property/` o `backend/tests/concurrency/`, accanto a `unit/` e
   `integration/`) così da poterli eventualmente eseguire con timeout/retry diversi dal
   resto della suite in CI.
5. **Documentare l'esito** (report testuale: quali invarianti sono state verificate, con
   quanti run, esito) come evidenza collegabile alla card.

## Tooling proposto

- **Hypothesis** (libreria Python di property-based testing, ben integrata con pytest):
  consigliata per generare sequenze di operazioni e input casuali sulle funzioni di
  dominio pure. Da aggiungere come dipendenza dev in `backend/pyproject.toml`.
- Per la concorrenza reale: `pytest` con `concurrent.futures.ThreadPoolExecutor` o
  processi separati che aprono connessioni DB indipendenti verso `postgres-test` (nessun
  nuovo servizio necessario, si riusa il servizio già presente in `compose.yaml`).

## Dati di test

- Lega di test con budget crediti noto, rosa parzialmente popolata, un turno con
  formazione salvata — riusabile dallo script di seed E2E previsto in EP12-01 se
  disponibile, altrimenti fixture dedicate minime.

## Criteri di accettazione (dalla card)

- Nessun saldo negativo, doppia assegnazione o risultato non deterministico.
- Evidenze collegate alla card.

## Test minimi richiesti

- Test unitari delle regole e validazioni di concorrenza introdotte.
- Test di integrazione e regressione sui casi limite (operazioni concorrenti al limite del
  budget, ultimo giocatore disponibile conteso, doppio salvataggio formazione simultaneo).

## Rischi e domande aperte

- I test di concorrenza reale possono essere flaky per natura (dipendono dal timing);
  serve una strategia di retry/ripetizione esplicita in CI per non introdurre falsi
  negativi che blocchino il gate `ci-success`.
- Da decidere se questi test girano ad ogni push (rischio: rallentano CI) o solo su
  branch `M5`/pre-release, coerente con la stessa domanda aperta in EP12-01.
