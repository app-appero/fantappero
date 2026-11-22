# Storico dei calciatori, media stagionale e Valore di mercato (1.3)

**Data:** 22 novembre 2026
**Decisioni:** Rosario, 21–22/11 (canvas «Proposte 1.3», scheda Valore di mercato; `docs/qa/known_issues.md`).
**Codice:** `backend/src/sports_data/season_stats/` (storico), `backend/src/market/valuation.py` (formule e costanti), `backend/src/market/valuation_service.py` (ricalcolo e letture), `backend/src/admin/season_history_service.py` (pannello operatore).

## In breve

- Le **due stagioni passate** (2024/25 e 2025/26) si scaricano **una volta** dal fornitore, con le statistiche di stagione di ogni calciatore.
- La **stagione in corso** (2026/27) e le prossime si calcolano dai **dati di FantApperò**: statistiche delle partite e nostri voti.
- Nelle liste del mercato ogni calciatore ha la **media stagionale** (verde se della stagione in corso, rossa con l'anno «25/26» se è quella della stagione scorsa) e il **Valore** in crediti della lega.
- La scheda calciatore ha lo **storico**: le due stagioni passate e quella in corso, dalla più recente.

## 1. Cosa si importa e da dove

Fornitore: API-Football v3, endpoint aggregato **`/players`** (statistiche di stagione, non partita per partita).

| Passo | Chiamata | Cosa dà |
| --- | --- | --- |
| Pagine di campionato | `/players?league=<id>&season=<anno>&page=<n>` per i 5 campionati (Premier League 39, La Liga 140, Serie A 135, Bundesliga 78, Ligue 1 61), 20 calciatori per pagina, fino a `paging.total` | Tutti i calciatori di quel campionato in quella stagione |
| Calciatori mancanti | `/players?id=<id fornitore>&season=<anno>`, uno per chiamata | Chi è nel listone di oggi ma in quella stagione giocava altrove (neopromosse, arrivi dall'estero, giovani) |

Anni del fornitore: `season=2025` è la 2025/26, `season=2024` la 2024/25.

Per ogni voce `statistics[]` della risposta si salva **una riga** per calciatore + stagione + club + competizione (un trasferimento a metà stagione dà due righe), nella tabella `athlete_season_stats` con `source = 'provider'`:

| Campo del fornitore | Colonna | Note |
| --- | --- | --- |
| `games.appearences` | `appearances` | Il fornitore scrive proprio «appearences» |
| `games.lineups` | `lineups` | Partite da titolare |
| `games.minutes` | `minutes` | |
| `games.rating` | `rating` | Media di stagione del fornitore: è una stringa e può essere `null` (resta vuota) |
| `goals.total`, `goals.assists` | `goals`, `assists` | |
| `goals.conceded`, `goals.saves` | `goals_conceded`, `saves` | |
| `penalty.saved` | `penalties_saved` | |
| `cards.yellow`, `cards.red` | `yellow_cards`, `red_cards` | |
| `team.id` / `team.name` | `club_provider_id`, `club_id`, `club_name` | `club_id` solo se il club è nel nostro catalogo, altrimenti resta il nome |
| `league.id` / `league.name` | `competition_provider_id`, `competition_id`, `competition_name` | Come sopra |
| — | `clean_sheets` | **Vuota**: l'aggregato di stagione del fornitore non ha le porte inviolate |

Ogni risposta passa da `store_provider_snapshot`, come le altre chiamate al fornitore (tabella `provider_snapshots`), e la riga di stagione ricorda da quale risposta viene (`snapshot_id`).

Le stagioni passate non cambiano: l'import è **una tantum** e **rieseguibile**. Ogni chiamata fatta è registrata in `athlete_season_import_fetches` (anche quando il fornitore non restituisce nulla): rilanciando, l'import salta quello che c'è già e non spende quota; le righe si aggiornano sulla chiave unica, senza doppioni.

## 2. Come lanciare l'import dal pannello operatore

Serve il permesso **`global:operate`** (operatore di piattaforma). A chiunque altro gli endpoint rispondono 403.

1. **Conta** — `POST /admin/listone/storico` con `{"seasonYear": 2026}` (`dryRun` vale `true` di default). Non chiama il fornitore: dice per ogni stagione quante pagine di campionato mancano, quanti calciatori del listone andranno cercati uno per uno, quante chiamate e quanti minuti servono (`estimate`).
   - Finché la prima pagina di un campionato non è scaricata, le pagine sono **stimate** (40 per campionato-stagione; `leaguePagesExact: false`). Dopo, il conto è esatto.
   - Finché mancano pagine di campionato, i calciatori da cercare sono una **stima** (25% del listone; `athletesToFillExact: false`).
2. **Avvia** — stessa chiamata con `{"seasonYear": 2026, "dryRun": false}` (facoltativo `"maxCalls"`, default 2000). Parte il job in background; la risposta ha il `jobId`. Se un import è già in corso restituisce quello, non ne avvia un secondo.
3. **Segui** — `GET /admin/listone/storico/{jobId}` (percentuale, fase, messaggio e alla fine il risultato); `GET /admin/listone/storico` dà l'import in corso a qualunque operatore, anche a chi non l'ha avviato.
4. **Riprendi** — se il risultato ha `stoppedReason`, rilancia il punto 2: riparte da dove si era fermato.
   - `max_calls`: raggiunto il tetto di chiamate di questa esecuzione;
   - `quota_reserve`: la quota giornaliera del fornitore è scesa sotto il **15%** del limite (margine per i giri live); rilanciare il giorno dopo;
   - `too_many_errors`: 10 errori di fila del fornitore; riprovare più tardi.

Il ritmo delle chiamate è quello del client del fornitore (limite al minuto delle impostazioni, default 300, e pausa automatica su 429). Alla fine dell'import si ricalcolano subito medie e Valore (`marketValues` nel risultato) e il risultato dice cosa resta (`remaining`).

Se manca la chiave del fornitore il job finisce subito con `errorCode: "provider_key_missing"`.

### Stima delle chiamate (una tantum)

| Voce | Conto | Chiamate |
| --- | --- | --- |
| Pagine di campionato | 5 campionati × 2 stagioni × ~40 pagine (~800 calciatori a 20 per pagina) | ~400 |
| Calciatori mancanti | ~25% di ~2.500 calciatori del listone × 2 stagioni (per la 2024/25 un po' di più: due giri di neopromosse) | ~1.250 |
| **Totale** | | **~1.650** |

A 300 chiamate al minuto sono circa 6 minuti; con il piano Pro (7.500 chiamate al giorno) basta un giorno, e l'import si ferma da solo prima di togliere quota ai giri live. Rilanciarlo dopo che ha finito costa **0 chiamate**. Il ricalcolo di medie e Valore non chiama mai il fornitore.

## 3. Stagione in corso: i dati di FantApperò

Per la 2026/27 (e le prossime) lo storico non viene dal fornitore. Per ogni calciatore + club + competizione si sommano le **partite finite** (FT, AET, PEN) della stagione:

- presenze (partite con minuti, o con voto), partite da titolare, minuti;
- gol, assist, gol subiti, parate, rigori parati, cartellini gialli e rossi (dalle statistiche della partita);
- **media voto = media dei nostri voti** (`player_match_ratings.display`) nelle partite con voto, e fantamedia;
- **porte inviolate** dei portieri, con la stessa regola del bonus (`fantasy_ratings.bonus.is_goalkeeper_clean_sheet`): portiere con voto e squadra a zero gol subiti nella partita. Per gli altri ruoli restano vuote.

I voti sono calcolati per lega (cambia solo la soglia minuti per avere il voto): per ogni calciatore-partita conta **un voto solo**, il più alto fra le leghe.

Scelta di efficienza (~2.500 calciatori): una sola query legge una riga per calciatore-partita della stagione, la somma e **riscrive** le righe `source = 'fantappero'` della stagione in `athlete_season_stats`. Le pagine leggono la tabella già pronta, mai i dati partita per partita.

Il ricalcolo gira:

- con il job periodico **«Medie e Valore di mercato»** (pannello operatore → Job; default ogni ora, `MARKET_VALUES_REFRESH_ENABLED`, `MARKET_VALUES_REFRESH_INTERVAL_SECONDS`): se voti, statistiche, storico e listone non sono cambiati dall'ultima volta non fa nulla, quindi dopo ogni giornata il Valore segue i voti nuovi;
- alla fine dell'import dello storico;
- a richiesta: `POST /admin/listone/valori/ricalcola` con `{"seasonYear": 2026}` (solo operatore; `"force": false` per saltare se nulla è cambiato).

## 4. Media stagionale nelle liste del mercato

| Caso | Media mostrata | `isCurrent` | Colore nella UI |
| --- | --- | --- | --- |
| Almeno un voto FantApperò nella stagione in corso | Media dei nostri voti della 2026/27 | `true` | verde |
| Nessun voto quest'anno, media del fornitore della 2025/26 | Media del fornitore, etichetta «25/26» | `false` | rossa |
| Nessuno dei due | nessuna (`null`) | — | — |

Con più righe nella stessa stagione (trasferimento) la media è pesata per presenze. Si mostra con due decimali.

## 5. Il Valore di mercato

Tutte le costanti sono in `backend/src/market/valuation.py` (con i test in `backend/tests/unit/market/test_valuation.py`).

1. **Percentile nel ruolo, stagione per stagione.** Per ogni stagione (due fa, la scorsa, quella in corso) e per ogni ruolo del listone (P, D, C, A, il ruolo ufficiale) la media di ogni calciatore si restringe verso la media del ruolo in base alle presenze con voto *n*:
   `media ristretta = (n × media + 8 × media del ruolo) / (n + 8)` — `SHRINK_APPEARANCES = 8`, così 3 belle partite non fanno un titolare.
   Poi si prende il **percentile** (0–1) della media ristretta fra i calciatori dello stesso ruolo con dati in quella stagione. Confrontare posizioni e non voti rende confrontabili le medie del fornitore (stagioni passate) e i nostri voti (stagione in corso).
2. **Stagione senza dati** = percentile `MISSING_SEASON_INDEX = 0,33` (sotto la mediana).
3. **Pesi** (canvas): stagione in corso fino al **50%**, che cresce con le presenze con voto e diventa pieno a **15** (`CURRENT_FULL_WEIGHT_APPEARANCES`); stagione scorsa **30%**, due stagioni fa **20%**. Il peso che manca alla stagione in corso va alle due passate in proporzione 30:20. Esempi: 0 presenze → 0% / 60% / 40%; 3 presenze → 10% / 54% / 36%; 15 o più → 50% / 30% / 20%.
4. **Curva convessa in crediti** del budget di riferimento (1000, il default delle leghe, `league_rules.total_credits`):
   `valore = 1 + (massimo del ruolo − 1) × p^2,4` — `CURVE_EXPONENT = 2,4`; massimo del ruolo (`TOP_REFERENCE_CREDITS`): P 30, D 32, C 48, A 66.
5. **Crediti della lega** = valore × budget della lega / 1000, arrotondato, almeno 1. Una lega da 500 crediti vede valori dimezzati.

Chi **non ha storico** ha p = 0,33, cioè il **valore base del ruolo**: P 3, D 3, C 4, A 6 (a budget 1000). Un calciatore entrato nel listone dopo l'ultimo ricalcolo ha il valore base fino al ricalcolo successivo.

### Tabella degli esempi (budget 1000 e 500)

| Caso | Ruolo | Indice p | Crediti a 1000 | Crediti a 500 |
| --- | --- | --- | --- | --- |
| Attaccante titolare nel top 5% (canvas ≈ 58) | A | 0,95 | 58 | 29 |
| Centrocampista di rotazione medio (canvas ≈ 12) | C | 0,545 | 12 | 6 |
| Nuovo arrivato con 3 belle partite (canvas ≈ 8) | A | 0,389 | 8 | 4 |
| Centrocampista titolare nel top 5% | C | 0,95 | 43 | 21 |
| Difensore titolare nel top 5% | D | 0,95 | 28 | 14 |
| Portiere titolare nel top 5% | P | 0,95 | 27 | 13 |
| Attaccante senza storico (base) | A | 0,33 | 6 | 3 |
| Centrocampista senza storico (base) | C | 0,33 | 4 | 2 |
| Difensore senza storico (base) | D | 0,33 | 3 | 2 |
| Portiere senza storico (base) | P | 0,33 | 3 | 2 |

Il nuovo arrivato: nessuna stagione passata (0,33 ciascuna, pesi 54% e 36%) e 3 partite ottime nella stagione in corso (percentile ~0,92 dopo la riduzione, peso 10%): p ≈ 0,1 × 0,92 + 0,9 × 0,33 ≈ 0,39. Il test `test_canvas_examples_on_a_realistic_listone` rifà gli esempi su un listone simulato di 2.300 calciatori.

Il Valore è un **prezzo consigliato**, non un minimo: la validazione delle offerte non cambia (partecipante almeno 1 credito, amministratore anche 0). Le regole di precompilazione del prezzo sono delle app.

## 6. Dove compare (API)

| Endpoint | Campi nuovi |
| --- | --- |
| `GET /leagues/{id}/listone` (Rosa e, in app, Svincolati) | `marketValue`, `seasonAverage` per ogni calciatore |
| Offerte di asta a buste e svincoli: `PUT/GET /leagues/{id}/mercato/asta/sessioni/{s}/offerte…`, `…/svincoli/sessioni/{s}/offerte…` | `marketValue`, `seasonAverage` su ogni offerta |
| Asta live: lotti (`…/asta-live/sessioni/{s}/lotti…`, nomina, rilanci, aggiudica) e `…/stato` (`currentLot`) | `marketValue`, `seasonAverage` sul lotto (il Valore è solo mostrato) |
| Proposte di scambio (`…/mercato/scambi/proposte…`) | `marketValue`, `seasonAverage` su `offeredAthletes[]` e `requestedAthletes[]` |
| Scheda calciatore `GET /leagues/{id}/calciatori/{athleteId}` | `marketValue`, `seasonAverage`, `career[]` |

`seasonAverage` = `{value, seasonYear, seasonLabel, isCurrent}`. Ogni riga di `career` ha stagione ed etichetta, `isCurrent`, `source` (`provider` o `fantappero`), club e competizione (id nostro se c'è, altrimenti solo il nome), presenze, minuti, `averageRating` (media voto), `votes`, `fantasyAverage`, gol, assist, gol subiti, parate, rigori parati, cartellini e `cleanSheets` (solo portieri della stagione in corso; `null` altrove). Tipi condivisi in `packages/contracts/src/athleteValue.ts`.

Il listone arriva intero e si ordina nelle app: «Ordina per media» usa `sortBySeasonAverageDesc` dei contratti (dalla media più alta, chi non ha media in fondo). Il backend non ordina.

## 7. Limiti noti

- Il Valore usa il **ruolo ufficiale** del listone, non l'eventuale ruolo cambiato da una lega.
- Se una lega ha una soglia minuti diversa, una partita con voto in un'altra lega conta come partita con voto (si prende il voto più alto fra le leghe).
- Le stagioni passate non hanno le porte inviolate (il fornitore non le dà nell'aggregato).
- Le statistiche di stagione del fornitore possono includere coppe e competizioni europee se il fornitore le riporta per quel calciatore: sono righe a parte nello storico e contano nella media pesata.
