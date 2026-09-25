# Registro open questions API-Football — input EP00-02

| Metadato | Valore |
| --- | --- |
| Origine | EP00-01 |
| Consumatore | EP00-02 (collaudo payload reali) |
| Versione | 0.1.0 |
| Vincolo | Nessuna chiave API, nessun payload grezzo con dati sensibili in repo. Nei test EP00-02 salvare solo fixture anonimizzate/congelate o path di campo + hash. |
| Corpus offline | `backend/tests/fixtures/api_football/` — vedi [`dataset_coverage.md`](./dataset_coverage.md) (**v0.2.0**, provenance `provider_v3`). Validare con `python backend/scripts/validate_sports_dataset.py`. |

Questo registro elenca **solo** ciò che la documentazione pubblica e i requisiti di prodotto non chiudono. Ogni voce va verificata su JSON reali dei cinque campionati.

### Nota B4 (24/09/2026) — stato reale del corpus di evidenza

Il corpus offline (`backend/tests/fixtures/api_football/manifest.json`, creato 2026-07-27) copre 20 fixture reali sui 5 campionati richiesti, con casi rari già taggati (`clean_sheet`, `own_goal`, `penalty_missed/saved/scored`, `red_card`, `substitution`) — è materiale sufficiente per chiudere diverse OQ P0 con evidenza reale, non sintetica. Due limiti concreti trovati leggendo il manifest:

1. **Endpoint mai acquisiti in questo corpus**: `/injuries`, `/predictions`, `/standings` (`endpoints_not_reperito` nel manifest). Senza questi dati **OQ-11 e OQ-14 non sono chiudibili** con il corpus attuale — serve una nuova acquisizione con chiave provider reale, che non può essere fatta da un'analisi di solo codice.
2. **Casi rari cercati ma non trovati**: `post_match_correction`, `postponement`. Le regole di codice per questi scenari esistono e sono testate con dati sintetici (vedi Blocco B1/B3), ma **manca ancora una prova su un payload reale del provider**.
3. **Il corpus non è collegato ai test delle regole di dominio**: `backend/tests/test_sports_dataset.py` valida solo l'integrità del corpus (checksum, conteggio fixture/leghe, assenza di segreti) — nessun test fa girare `fantasy_ratings/bonus.py` o `fantasy_ratings/eligibility.py` sui payload reali per produrre l'evidenza "Pass/Fail" richiesta dalla checklist EP00-02. Il materiale grezzo c'è, il collaudo descritto nella checklist sotto non risulta ancora eseguito/tracciato.

Per le OQ che restano genuinamente aperte (OQ-08, OQ-09, OQ-10, OQ-11, OQ-12, OQ-13, OQ-14) non sono state inventate risposte: OQ-09 in particolare è esplicitamente una decisione di prodotto ("non inventare pesi qui" nel testo originale) che richiede il team, non un'analisi di codice.

## Legenda priorità

| Priorità | Significato |
| --- | --- |
| **P0 — Bloccante** | Senza risposta non si chiude bonus/malus, listone o Rating Beta. |
| **P1 — Alto** | Possibile mitigation admin/UX, ma va misurato prima del go-live. |
| **P2 — Accettabile** | Rischio tollerato nell’MVP se mitigation documentata. |

---

## Domande aperte

### OQ-01 — Mapping posizione provider → ruolo FantApperò (P–D–C–A)

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | `/players`, `/players/squads` (`statistics[].games.position`, `players[].position`) |
| Domanda | Quali valori esatti compaiono nei 5 campionati e come si mappano 1:1 a P/D/C/A? Esistono ruoli ambigui (WB, DM, AM, CF…)? |
| Impatto | FR-ROS-01, vincoli rosa 3P–11D–11C–10A |
| Evidenza richiesta EP00-02 | Inventario valori `position` su campione squadre; proposta tabella mapping; casi da override admin |
| Criterio chiusura | Tabella versionata + policy “un solo ruolo attivo per listone” |
| Esito EP04-04 | **Chiuso (MVP)** — mapping `v1.0.0` in `sports_data.listone.mapping`; listone ufficiale `role_assignments`; override lega versionato con efficacia post-avvio dal turno successivo. Vedi [`../operations/sports_listone.md`](../operations/sports_listone.md). |

### OQ-02 — Autogol univoco

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | `/fixtures/events` (`type=Goal`, `detail=Own Goal`) ± stats |
| Domanda | `Own Goal` è sempre presente e distinto da `Normal Goal`? L’autogol appare anche in `goals.total` del marcatore sbagliato? |
| Impatto | FR-SCO-02 (−2); rischio falso +3 |
| Evidenza richiesta EP00-02 | ≥1 caso per campionato se disponibile; confronto events vs `/fixtures/players` |
| Criterio chiusura | Regola: bonus gol solo se `detail=Normal Goal` o `Penalty` (se confermato); autogol solo `Own Goal` |
| Esito EP00-03 | **Chiuso** — vedi ADR-0002 / `event_precedence_rules.md`: solo `Own Goal` → `own_goal` |

### OQ-03 — Coerenza assist events ↔ stats

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | `/fixtures/events.assist` vs `/fixtures/players.goals.assists` |
| Domanda | In che % dei casi divergono? Chi vince in caso di conflitto post-correzione? |
| Impatto | FR-SCO-02 (+1); FR-DAT-01 |
| Evidenza richiesta EP00-02 | Matrice su 10–20 fixture concluse (Architettura §13.3) |
| Criterio chiusura | Algoritmo deterministico documentato (es. events primari, stats come watchdog → Provvisorio) |
| Esito EP00-03 | **Chiuso** — events primari, stats watchdog; mismatch → `assist_count_mismatch` / Provvisorio |

### OQ-04 — Rigore parato

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | Candidato `/fixtures/players.penalty.saved`; events `detail` da ispezionare |
| Domanda | Dove appare in modo affidabile il rigore parato? È distinguibile da palo/fuori / `Missed Penalty`? A quale `player.id` (portiere) è agganciato? |
| Impatto | FR-SCO-02 (+3 portiere) |
| Evidenza richiesta EP00-02 | Fixture con rigore parato reale; dump campi (solo path+valori non sensibili) |
| Criterio chiusura | Campo canonico + test golden |
| Esito EP00-03 | **Chiuso** — primario `players.penalty.saved`; nessun `detail` events nel corpus |

### OQ-05 — Rigore sbagliato e doppia ammonizione

| Campo | Valore |
| --- | --- |
| Priorità | P0 (missed) / P0 regolamentare (yellow-red) |
| Endpoint | Events `Missed Penalty`; `Yellow Card` / `Red Card` / `Yellow-Red Card`; stats `penalty.missed`, `cards.*` |
| Domanda | (a) Missed penalty sempre agganciato al tiratore? (b) Su `Yellow-Red` si applica solo −1 espulsione o anche −0,5 ammonizione? |
| Impatto | FR-SCO-02; eccezione FR già aperta sul regolamento esecutivo |
| Evidenza richiesta EP00-02 | Casi reali + decisione prodotto esplicita per (b) |
| Criterio chiusura | Tabella eventi → delta fantavoto senza ambiguità |
| Esito EP00-03 | **Parziale** — classificazione miss/save/off-target chiusa; regola cumulativa yellow-red resta aperta |

### OQ-06 — Chiave `provider_event_key` e correzioni post-FT

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | `/fixtures/events` (+ re-fetch) |
| Domanda | Il provider espone un ID evento stabile? Se no, quale composizione (fixture+elapsed+extra+type+detail+player+assist+comments) resta stabile dopo correzione/VAR? |
| Impatto | Idempotenza FR-DAT-01; no doppio bonus |
| Evidenza richiesta EP00-02 | Stessa fixture pre/post correzione; confronto set eventi |
| Criterio chiusura | Funzione chiave + test “stessa risposta due volte” e “correzione aggiorna stessa riga” |
| Esito EP00-03 | **Chiuso per composizione + idempotenza** — `provider_event_key` in `normalization/keys.py`; correzioni post-FT (doppio snapshot) ancora non nel corpus |

### OQ-07 — Minuti, recupero, senza voto

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | `/fixtures/players.games.minutes`, `games.substitute`; events `subst` |
| Domanda | I minuti includono recupero? Subentrati al 90+ hanno `minutes` > 0? Giocatori in panchina senza entrare compaiono nel payload stats? |
| Impatto | Soglia 15'; FR-SCO-01; FR-SUB-01; “senza voto” |
| Evidenza richiesta EP00-02 | Titolare 90, sub 10, sub recupero, non sceso in campo |
| Criterio chiusura | Regola deterministica minuti + eventi rilevanti sotto soglia |
| Esito B4 (24/09/2026) | **Chiuso** — validato su payload reali del corpus offline (10 ingressi in recupero del secondo tempo trovati su tutte le 20 fixture, `matches/*/fixtures_events.json`+`fixtures_players.json`). Risposta empirica: `minutes` **è sempre 1** per un ingresso al 90+, mai 0 e mai proporzionale al recupero realmente giocato — quindi la sola soglia minuti classificherebbe erroneamente questi casi come "senza voto" se non ci fosse una regola dedicata. `fantasy_ratings/eligibility.py` gestisce già correttamente il caso (`is_second_half_stoppage` + `stoppage_entry_player_ids_from_payload`, poi `evaluate_eligibility` richiede un evento rilevante per chi entra in recupero, indipendentemente da `minutes`). Test aggiunto: `backend/tests/unit/fantasy_ratings/test_eligibility.py::test_real_stoppage_entrants_get_a_small_nonzero_minutes_value`. Non ancora verificato: giocatori in panchina mai entrati (se compaiono o meno nel payload stats) — nessun caso di questo tipo trovato nel corpus attuale. |

### OQ-08 — Coverage e completezza stats sui 5 campionati

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | `/leagues` coverage + `/fixtures/players` |
| Domanda | Per stagione attiva, `statistics_players` / `events` / `lineups` / `injuries` sono `true`? Quali campi stats risultano frequentemente `null`? |
| Impatto | Rating Beta e bonus |
| Evidenza richiesta EP00-02 | Tabella coverage per league 39/140/135/78/61; % null per campo candidato Rating |
| Criterio chiusura | Lista campi ammessi in formula v1 vs esclusi per qualità |
| Esito B4 (24/09/2026) | **Parziale — chiuso per i campi della formula v1 (bonus/malus), aperto per la calibrazione Rating Beta (dipende da OQ-09).** Tabella % null calcolata sui payload reali del corpus offline (694 entry giocatore-partita, 5 campionati): `goals.total` 91-94% null, `goals.assists` 57-98% null, `penalty.saved` 93-95% null, `cards.red`/`cards.yellow`/`penalty.missed` ~0% null, `games.minutes`/`games.rating` 8-22% null. Verificato che gli alti tassi di null su `goals.total`/`goals.assists`/`penalty.*`/`cards.red` **non sono dati mancanti**: sono campi di conteggio dove il provider usa `null` per "zero occorrenze" (la maggioranza dei giocatori non segna/assiste/para un rigore in una partita), e `fantasy_ratings/input.py::_as_int` li tratta già correttamente come 0. `goals.conceded` non viene letto dal payload grezzo per calcolare la porta inviolata: `mapping.py::team_goals_conceded` lo deriva dal punteggio reale della fixture, aggirando del tutto la null-rate variabile per lega (0-43%) di quel campo. L'unico null "vero" (dato non applicabile, non zero) è `games.minutes`/`games.rating` per i convocati in panchina mai entrati — verificato 1:1 con `games.substitute=true` su tutto il corpus, nessuna eccezione. Test aggiunti in `backend/tests/unit/fantasy_ratings/test_real_corpus_coverage.py`. **Resta aperto**: la lista completa dei campi (saves, shots, passes, tackles, duels, fouls) per la futura Rating Beta è materia di OQ-09, non misurabile qui perché la formula v2 non è ancora definita. |

### OQ-09 — Calibrazione input Rating Beta (non inventare pesi qui)

| Campo | Valore |
| --- | --- |
| Priorità | P0 (prodotto) / esecuzione dopo OQ-07/08 |
| Endpoint | `/fixtures/players` |
| Domanda | Quali sottoinsiemi di stats (saves, shots, passes, tackles, duels, fouls, …) entrano nella v1 Beta per P/D/C/A? |
| Impatto | FR-SCO-01; Master: formula concettuale, coefficienti aperti |
| Evidenza richiesta EP00-02 | Dataset freeze 10–20 partite; notebook calibrazione **fuori** da questo file |
| Criterio chiusura | Formula versionata pubblicata; rating provider solo benchmark |

### OQ-10 — Lineup ufficiali: timing e definizione “convocato”

| Campo | Valore |
| --- | --- |
| Priorità | P1 |
| Endpoint | `/fixtures/lineups` |
| Domanda | Minuti medi pre-kickoff di prima pubblicazione per campionato? `substitutes` è sempre popolato? Un giocatore solo in events ma non in lineup conta come convocato? |
| Impatto | FR-RIN-01 (6 d’ufficio); FR-AI-01 |
| Evidenza richiesta EP00-02 | Campionamento pre-match; policy booleana `was_called_up` |
| Criterio chiusura | Policy scritta; se dati assenti → eccezione admin (già FR) = rischio accettabile R-01 |
| Esito B4 (24/09/2026) | **Parziale.** Caso reale trovato nel corpus (fixture 37834, giocatore 68091): un centrocampista che ha giocato **90 minuti interi** (`minutes: 90`, `rating: 6.9`) è **assente dalla lineup ufficiale** (`startXI`+`substitutes`) di quella fixture — conferma diretta che "solo in stats, non in lineup" **succede davvero**, non è un caso teorico. Buona notizia: lo scoring non dipende dalla lineup — `fantasy_ratings/input.py::iter_players_from_payload` legge direttamente `/fixtures/players`, quindi questo tipo di lacuna **non blocca né distorce il fantavoto**. L'assenza totale di lineup (non il singolo giocatore mancante) è già un'eccezione admin reale: `sports_data/quality/rules.py::detect_missing` segnala `MISSING_LINEUPS` (severità WARNING) quando `lineup_count == 0` a partita conclusa — soddisfa la parte "se dati assenti → eccezione admin" del criterio di chiusura. La lineup ufficiale è invece usata per la formazione automatica IA (EP13-P05, `fantasy_lineups/ai_service.py`), che ha un percorso di esito `"incomplete"` tracciato a metriche quando i dati sono parziali — non ho verificato in profondità la qualità di questo fallback quando la lineup è presente-ma-sbagliata (come nel caso reale trovato) invece che del tutto assente. **Resta aperto**: nessuna policy booleana `was_called_up` esplicita esiste nel codice; il timing medio di prima pubblicazione pre-kickoff per campionato non è misurabile da un corpus statico post-partita, servirebbe monitoraggio in produzione su partite live. |

### OQ-11 — Infortuni vs squalifiche e overlapping `/sidelined`

| Campo | Valore |
| --- | --- |
| Priorità | P1 |
| Endpoint | `/injuries` (`type`, `reason`); eventuale `/sidelined` (fuori scope EP00-01 ma correlato) |
| Domanda | `type` distingue sempre Injury/Suspension? `reason` è stabile o free-text? Serve `/sidelined` nell’MVP? |
| Impatto | Esclusione 6 d’ufficio; IA |
| Evidenza richiesta EP00-02 | Campione injuries per league; decisione su `/sidelined` |
| Criterio chiusura | Enum interno; niente parsing NLP di `reason` |
| Esito B4 (25/09/2026) | **Chiuso.** Verificato con chiamate reali all'endpoint (chiave provider già configurata in locale), non solo lettura di codice. **`type` NON distingue Injury/Suspension** come presupponeva la domanda: ha solo due valori reali, `"Missing Fixture"` (assenza certa) e `"Questionable"` (dubbio). La distinzione va derivata da `reason`, che **non è testo libero**: solo 41 valori distinti osservati su un campione di 3168 voci reali (Premier League 2024) — enum interno costruibile senza parsing NLP. **Trovato un caso reale e riproducibile di dato mancante**: interrogando `/injuries` per la Lazio (squadra 487, stagione 2026) risultano disponibili 4 giocatori su 5 di un riferimento noto; il quinto (Filipe Bordon, id provider 407916, confermato in rosa) **non compare mai**, nemmeno cercandolo per ID diretto su due stagioni — conferma che l'endpoint può mancare selettivamente giocatori realmente indisponibili. **Implementato**: nuovo modulo `sports_data/availability/` (modello `PlayerAvailability`, enum `PlayerAvailabilityCategory` in `database/enums.py`, classificazione `reason`→categoria in `classify.py` con tabella fissa dei 41 valori reali + fallback deterministico per valori nuovi, sync idempotente da `/injuries`, migrazione `2fb4800de433`). La funzione di lettura `is_confirmed_unavailable` ritorna esplicitamente `None` quando non trova nulla, **mai un "disponibile" presunto** — è la policy resa necessaria dal caso Bordon. Non collegato (deliberatamente, per non allargare lo scope) a `eligibility.py` o alla selezione IA: resta un consumo futuro. Test: `backend/tests/unit/sports_data/test_availability_classify.py`, `backend/tests/integration/sports_data/test_availability_sync.py`. Migrazione verificata up/down/drift-check su database isolato. |

### OQ-12 — Transfer Loan / temporanei / uscita dai 5 campionati

| Campo | Valore |
| --- | --- |
| Priorità | P1 |
| Endpoint | `/transfers`, `/players/squads` |
| Domanda | Come rilevare in modo affidabile “uscita dai cinque campionati” per credito 100%? Come trattare Loan e date mancanti? `/players/squads` senza `season` basta per membership corrente? |
| Impatto | FR-MKT-02, FR-ROS-01 |
| Evidenza richiesta EP00-02 | Casi trasferimento inter-lega big-5, fuori big-5, loan |
| Criterio chiusura | Regole auto vs coda admin (allineate a FR-MKT-02) |
| Esito B4 (25/09/2026) | **Parziale.** La regola "auto vs coda admin" è già decisa e implementata: `roster/validators.py::transfer_requires_admin_review` marca `loan`/`n/a` come non affidabili per svincolo automatico (commento nel codice cita esplicitamente OQ-12). L'uscita dai 5 campionati è rilevata correttamente per costruzione: `_apply_transfer_membership_effects` disattiva la membership d'origine ad ogni trasferimento, e il club di destinazione risolve a `None` se fuori dai 5 campionati (solo quei club sono nel catalogo) — nessun bisogno di un controllo esplicito aggiuntivo. `/players/squads` è chiamato correttamente senza `season` (`{"team": club.provider_id}`): è per design l'endpoint "squadra attuale" del provider, non un limite da aggirare. **Gap reale trovato**: il flag `requires_admin_review` viene scritto sul record `Transfer` ma **non è mai esposto** — nessun endpoint admin, nessuna coda, nessuna UI lo legge. Esiste anche un percorso di credito 100% dedicato (`MarketReleaseReason.LEAGUE_EXIT`, `league_exit_refund_percent` default 100 su `LeagueRules`), ma è **azionato solo manualmente** da chi effettua lo svincolo scegliendone il motivo — non è collegato automaticamente al rilevamento di trasferimento/uscita. Per design è corretto che l'azione finale resti umana (coerente con il pattern già visto per OQ-11); il gap è che oggi non c'è nulla che segnali all'admin *quali* trasferimenti aspettano una decisione. |

### OQ-13 — Porta inviolata portiere

| Campo | Valore |
| --- | --- |
| Priorità | P1 |
| Endpoint | `/fixtures/players.goals.conceded` ± score fixture ± minutes |
| Domanda | CS richiede 90 minuti? Vale se subentra e non subisce? Partita sospesa? |
| Impatto | FR-SCO-02 (+1) |
| Evidenza richiesta EP00-02 | Casi P titolare 0 concessi; P sub; partita SUSP |
| Criterio chiusura | Regola booleana versionata |

### OQ-14 — Predictions e standings come segnale IA

| Campo | Valore |
| --- | --- |
| Priorità | P2 |
| Endpoint | `/predictions`, `/standings` |
| Domanda | Copertura % fixture weekend tipico? Quali campi esporre allo staff IA senza implicare certezza? |
| Impatto | FR-AI-*; Master: predizioni non fatti |
| Evidenza richiesta EP00-02 | Smoke test coverage; UX copy “probabilità/segnale” |
| Criterio chiusura | Snapshot etichettato `signal`; assenza = IA degradata OK |

### OQ-15 — Identificativi season e ID leghe

| Campo | Valore |
| --- | --- |
| Priorità | P1 |
| Endpoint | `/leagues` |
| Domanda | Confermare ID 39/140/135/78/61 e `season` corrente; verificare delay di popolazione fixture a inizio stagione |
| Impatto | Sync bootstrap |
| Evidenza richiesta EP00-02 | Call `/leagues?id=&season=`; salvare solo metadati coverage |
| Criterio chiusura | Config piattaforma versionata |
| Esito B4 (24/09/2026) | **Parziale** — ID leghe confermati: `MVP_LEAGUE_IDS = (39, 140, 135, 78, 61)` in `backend/src/sports_data/provider/constants.py`, config versionata e unica, riusata coerentemente da `catalog/sync.py`, `fixtures/sync.py`, `roster/sync.py`, `scheduler/runner.py`. `season` corrente resta invece per-lega (`league.season_year`), non una costante piattaforma: nessuna evidenza trovata su verifica del delay di popolazione fixture a inizio stagione. |

---

## Checklist esecuzione EP00-02

1. Autenticazione solo in secret manager / env locale; mai commit.
2. Congelare 10–20 fixture FT distribuite sui 5 campionati (Architettura §13.3), includendo: sub tardivo, rigore, autogol, espulsione, assist contestato, clean sheet, PST, correzione post-FT.
3. Per ogni OQ P0: allegare esito Pass/Fail + path campi osservati (niente payload interi in git se contengono dati non necessari; preferire summary).
4. Aggiornare la matrice EP00-01 (bump versione) quando un gap P0 chiude.
5. Distinguere ancora **gap bloccante** vs **rischio accettabile** nel report EP00-02.

## Tracciabilità

| Artefatto | Path |
| --- | --- |
| Matrice | [`api_football_requirement_matrix.md`](./api_football_requirement_matrix.md) |
| ADR confine provider | [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md) |
| Precedenza eventi (EP00-03) | [`event_precedence_rules.md`](./event_precedence_rules.md) |
| ADR precedenza eventi | [`../adr/ADR-0002-sports-event-precedence.md`](../adr/ADR-0002-sports-event-precedence.md) |
