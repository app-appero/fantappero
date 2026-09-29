# Registro dei requisiti — chiusura Fase 1 (A1 / EP13-02)

**Versione:** 0.1 — bozza automatica di prima passata
**Data:** 24 settembre 2026
**Commit di riferimento:** `98fa151` (HEAD al momento della generazione)
**Corrisponde a:** Blocco A1 del piano `FantAppero_Piano_Chiusura_Fase_1.md` e alla card `EP13-02 — Inventario normativo e registro di tracciabilità totale` (`docs/doc_fantapperò/FantAppero_Pacchetto_Chiusura_Beta_M5.1_v0.2/`).

## 1. Cosa è (e cosa non è) questo documento

Questa è una **bozza di prima passata generata automaticamente**, non il registro finale richiesto da EP13-02. La card EP13-02 stima 2-4 giorni di lavoro e richiede: inventario di tutti gli artefatti documentali (baseline dichiarata 93), evidenze manuali/E2E per ogni riga, risoluzione delle contraddizioni, owner assegnati. Nessuna di queste cose è ancora stata fatta qui.

Quello che questo documento fa:

- estrae in modo sistematico **tutte le 92 card** dei pacchetti Trello del repository (72 card M0.5–M5, 7 card Pre-M5.1 + 1 discovery Fase 2, 12 card EP13/M5.1);
- incrocia ogni codice con la **storia git** (`git log --all --oneline`, 110 commit totali) per trovare un commit dedicato che la implementa;
- dove non trova un commit dedicato, verifica se il **modulo di codice corrispondente esiste** nella struttura del repository (`backend/src`, `apps/web/src`, `apps/mobile/src`);
- assegna uno **stato preliminare** secondo l'enum ufficiale del piano (`IMPLEMENTED_VERIFIED`, `MVP_REMEDIATION`, `PHASE2_BACKLOG`, `SUPERSEDED`, `REJECTED`, `HUMAN_OPERATIONAL_GATE`, `EVIDENCE_TEMPLATE`), usando **`EVIDENCE_TEMPLATE` come default onesto** ovunque esista solo un indizio automatico (commit o modulo) ma non una prova manuale/di test verificata da una persona. Nessuna riga è stata marcata `IMPLEMENTED_VERIFIED` in automatico: farlo violerebbe la regola esplicita del piano ("non esistono funzionalità dichiarate completate ma disponibili soltanto in demo").

Due righe (`EP12-01`, e implicitamente il gruppo `EP13-*`) hanno uno stato diverso da `EVIDENCE_TEMPLATE` perché **verificate direttamente in questa sessione**, non per inferenza automatica — vedi §3.

## 2. Legenda

| Colonna | Significato |
|---|---|
| Codice | Identificativo della card (EPxx-yy) |
| Milestone | Lista Trello di provenienza (M0.5…M5, Pre-M5.1, Fase 2, M5.1) |
| Must/Should | Priorità dichiarata nei Labels del CSV sorgente |
| Titolo | Titolo della card |
| Aree | Aree tecniche dichiarate (Backend/Frontend/Database/Infrastructure/QA/AI/Mobile...) |
| Evidenza automatica | Cosa ha trovato l'incrocio automatico (commit, modulo di codice, o assenza) |
| Confidenza | Quanto è specifico il segnale automatico: **ALTA** = commit dedicato con codice esplicito o verifica diretta in sessione; **MEDIA** = solo commit di milestone squashato o modulo generico presente; **BASSA** = nessun riscontro trovato |
| Stato preliminare | Valore dell'enum ufficiale, da confermare/correggere da una persona |

**Limite noto e già segnalato dal piano stesso** (Blocco B1, riga 173): la cronologia git per M1 e M2 (card `EPUI-*`, `EP02-*`…`EP06-*`, 38 card) è squashata in pochi commit di milestone (`a53a6b3`, `6d7ec0e`, `b343888`, `460339d`, `7850b68`, `afd3815`) senza granularità per singola card. Per queste righe l'evidenza automatica è strutturale (il modulo di codice esiste) ma non prova che quella specifica card sia stata completata secondo i suoi criteri di accettazione. M3–M5 (`EP07`–`EP12`, 34 card) hanno invece quasi tutte un commit dedicato con il codice nel messaggio.

## 3. Scostamenti noti rispetto all'evidenza puramente automatica

Durante l'analisi del piano di chiusura in questa stessa sessione sono state raccolte prove dirette (non solo inferenza da git log) su alcuni punti, riportate nella tabella:

- **EP12-01 (Suite end-to-end critica):** il job CI `e2e-critical-flow` è marcato `informative` in `.github/workflows/ci.yml`, quindi non blocca il merge; copre solo 2 flussi (`critical-flow-states`, `registration-to-league`), solo web/Playwright; non esiste alcun E2E mobile. Per questo è classificata `MVP_REMEDIATION` e non `EVIDENCE_TEMPLATE`.
- **EP13-01…EP13-12 (pacchetto M5.1):** nessun commit trovato in git log — confermano che il piano di chiusura Fase 1 (questo stesso documento e i blocchi B–G) non è ancora stato eseguito. Classificate `MVP_REMEDIATION` perché rappresentano lavoro di chiusura non ancora iniziato, non semplice mancanza di prova.
- **EP12-02 (Test proprietà e concorrenza):** dei 4 scenari di concorrenza critici del piano, 3 (waiver, approvazione admin trade, omologazione/ricalcolo) sono risultati protetti dal lock già esistente; il quarto (kickoff che cambia durante il salvataggio della formazione) aveva invece una vera finestra di corsa, riprodotta con un test dedicato e corretta in `fantasy_lineups/service.py` — unico caso in questo blocco con un bug reale, non solo una verifica.
- **9 domande aperte su dati reali API-Football** (`docs/data/api_football_open_questions.md`, OQ-07…OQ-15: minuti/recupero, copertura 5 campionati, calibrazione Rating Beta, lineup ufficiali, infortuni/squalifiche, trasferimenti, porta inviolata, predictions IA, ID season/leghe) restano senza `Esito` nel documento sorgente. Toccano soprattutto le card `EP04-01`, `EP04-02`, `EP04-03`, `EP04-05` e, per la porta inviolata, `EP07-03`. Non sono card a sé stanti nel registro Trello, quindi non hanno una riga propria: vanno aggiunte come voci "decisione normativa non trasformata in card" nel registro definitivo, come richiesto esplicitamente da EP13-02.

## 4. Conteggio stati preliminari (92 righe)

| Stato preliminare | Righe | Significato pratico |
|---|---:|---|
| `EVIDENCE_TEMPLATE` | 66 | Codice presumibilmente presente, manca prova manuale/test verificata da una persona |
| `MVP_REMEDIATION` | 13 | Gap confermato direttamente in questa sessione (E2E non bloccante, pacchetto EP13 non iniziato) |
| `IMPLEMENTED_VERIFIED` | 13 | Verificate con lettura di codice + test esistenti/aggiunti durante il Blocco B (B1: EP04-07, EP06-03, EP06-05, EP06-06, EP06-07; B2: EP07-05, EP07-07, EP13-P02; B3: EP03-06, EP13-P03; B4: EP07-02, EP07-03; B5: EP12-02) |
| `PHASE2_BACKLOG` | 1 | Dichiarata Fase 2 dalla fonte stessa (`EP13-F01`, discovery club/formazione personale) |

Aggiornamento 24/09/2026 (Blocco B1+B2+B3): 10 righe sono passate da `EVIDENCE_TEMPLATE` a `IMPLEMENTED_VERIFIED` dopo lettura diretta del codice e dei test esistenti — non è più una fotografia puramente automatica, è in corso la verifica con prova richiesta da EP13-02. Nota: per B3 la verifica è stata **volutamente limitata alla sola lettura**, su richiesta esplicita — nessuna modifica al codice del calendario/turni europei, area su cui è già stato investito lavoro significativo di messa a punto.

Aggiornamento 26/09/2026 (Blocco B5): EP12-02 passa da `EVIDENCE_TEMPLATE` a `IMPLEMENTED_VERIFIED` dopo aver testato direttamente i 4 scenari di concorrenza critici del piano — a differenza degli altri blocchi, qui è emerso un bug reale (non solo una verifica), corretto con conferma esplicita dell'utente prima di toccare il codice.

## 5. Registro

| Codice | Milestone | Must/Should | Titolo | Aree | Evidenza automatica | Confidenza | Stato preliminare |
|---|---|---|---|---|---|---|---|
| EPUI-01 | M0.5 — Ready | Must | Identità visiva e direzione UI | EPUI, Frontend | a53a6b3 design M0.5 (commit unico non granulare); docs/design/ presente | MEDIA (commit di milestone, non per card) | EVIDENCE_TEMPLATE |
| EPUI-02 | M0.5 — Ready | Must | Design system web | EPUI, Frontend | a53a6b3 design M0.5 (commit unico non granulare); docs/design/ presente | MEDIA (commit di milestone, non per card) | EVIDENCE_TEMPLATE |
| EPUI-03 | M0.5 — Ready | Must | Layout, navigazione e componenti applicativi base | EPUI, Frontend | a53a6b3 design M0.5 (commit unico non granulare); docs/design/ presente | MEDIA (commit di milestone, non per card) | EVIDENCE_TEMPLATE |
| EPUI-04 | M0.5 — Ready | Must | Wireframe delle schermate principali | EPUI, Frontend | a53a6b3 design M0.5 (commit unico non granulare); docs/design/ presente | MEDIA (commit di milestone, non per card) | EVIDENCE_TEMPLATE |
| EPUI-05 | M0.5 — Ready | Must | Shell responsive della web app | EPUI, Frontend, QA | a53a6b3 design M0.5 (commit unico non granulare); docs/design/ presente | MEDIA (commit di milestone, non per card) | EVIDENCE_TEMPLATE |
| EP02-01 | M1 — Ready | Must | Registrazione, login e recupero accesso | EP02, Backend, Frontend | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src. Estensione 29/09/2026: aggiunto login/registrazione con Google (`POST /auth/google`, `auth/google_oauth.py`), portata dentro Fase 1 su richiesta esplicita dell'utente, web+mobile Android; collegamento automatico all'account esistente per email Google già registrata. Richiede credenziali OAuth reali (Google Cloud Console) e ri-approvazione della privacy notice (F2, `da2ba59`) prima del pilot — non ancora fatto. | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP02-02 | M1 — Ready | Must | Profilo e preferenze | EP02, Backend, Frontend | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP02-03 | M1 — Ready | Must | Ruoli applicativi e autorizzazioni | EP02, Backend, QA | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP02-04 | M1 — Ready | Should | Eliminazione ed esportazione account | EP02, Backend, Frontend | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP03-01 | M1 — Ready | Must | Creazione lega | EP03, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP03-02 | M1 — Ready | Must | Configurazione regolamento | EP03, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP03-03 | M1 — Ready | Must | Inviti e ingresso | EP03, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP03-04 | M1 — Ready | Must | Gestione partecipanti | EP03, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP03-05 | M1 — Ready | Must | Stati e avvio stagione | EP03, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP03-06 | M1 — Ready | Must | Calendario scontri diretti | EP03, Backend, Frontend, Database | VERIFICATO B3 (24/09/2026, SOLO LETTURA su richiesta esplicita): `leagues/calendar_planning.py` — generazione round-robin con bilanciamento casa/trasferta via decomposizione euleriana (risolve un ottimo locale documentato del greedy precedente a 7 partecipanti), `assert_plan_invariants` invocato anche in produzione (`calendar_service.py:170`, non solo nei test) verifica: nessuna squadra gioca due volte a giornata, nessuno scontro senza avversario, finestre distinte e cronologiche, copertura completa degli accoppiamenti sui cicli interi, riposi equi. Test parametrizzati su **4-10 partecipanti** (oltre il minimo 4/5/8/10 richiesto dal piano). | ALTA (lettura codice + test esistenti, nessuna modifica) | IMPLEMENTED_VERIFIED |
| EP04-01 | M1 — Ready | Must | Adapter API-Football | EP04, Backend, Database, Infrastructure | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP04-02 | M1 — Ready | Must | Catalogo competizioni e stagioni | EP04, Backend, Database, Infrastructure | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP04-03 | M1 — Ready | Must | Calciatori, rose reali e trasferimenti | EP04, Backend, Database, Infrastructure | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP04-04 | M1 — Ready | Must | Listone e ruoli P–D–C–A | EP04, Backend, Database, Infrastructure | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP04-05 | M1 — Ready | Must | Fixture, eventi, lineup e statistiche | EP04, Backend, Database, Infrastructure | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP04-06 | M1 — Ready | Must | Scheduler pre/live/post partita | EP04, Backend, Database, Infrastructure | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP04-07 | M1 — Ready | Must | Pannello qualità dati | EP04, Backend, Database, Infrastructure | VERIFICATO B1 (24/09/2026): modulo reale `sports_data/quality/` con `rules.py` (`detect_missing`, `detect_delays`, `detect_conflicts`, `detect_corrections`, fingerprint per dedupe), `service.py`, `router.py` (API), `tasks.py` (retry). Test unitari (`test_quality_rules.py`) + integrazione (`test_quality_panel.py`). Copre anomalie operative di sync dati (mancanti/in ritardo/in conflitto/corretti), non le 9 domande normative aperte in `docs/data/api_football_open_questions.md` (OQ-07…15), che restano un gap B4 distinto. | ALTA (lettura codice + test esistenti) | IMPLEMENTED_VERIFIED |
| EP05-01 | M2 — Ready | Must | Entità squadra fantasy e rosa | EP05, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP05-02 | M2 — Ready | Must | Ledger crediti | EP05, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP05-03 | M2 — Ready | Must | Inserimento manuale rose | EP05, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP05-04 | M2 — Ready | Must | Import CSV con anteprima | EP05, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP05-05 | M2 — Ready | Must | Validazione composizione rosa | EP05, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP05-06 | M2 — Ready | Must | Storico rosa e snapshot | EP05, Backend, Frontend, Database | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP06-01 | M2 — Ready | Must | Generazione turno europeo | EP06, Backend, Frontend, QA | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP06-02 | M2 — Ready | Must | Moduli validi e schieramento | EP06, Backend, Frontend, QA | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP06-03 | M2 — Ready | Must | Formazione progressiva per kickoff | EP06, Backend, Frontend, QA | VERIFICATO B1 (24/09/2026): lock individuale per-atleta calcolato server-side da `fixture.kickoff_at` corrente in `fantasy_lineups/rules.py::is_athlete_kickoff_locked` + `service.py::_is_row_locked`, ricalcolato ad ogni richiesta di lettura/scrittura (`_sync_round_kickoffs`). Scrittura bloccata da eccezione reale (`assert_progressive_lock`, `assert_bench_order_lock` in `service.py:296-306`), non solo da UI disabilitata. Test unitari: `backend/tests/unit/fantasy_turns/test_rules.py::test_reconcile_fixture_kickoff_lock_*`. Difetto minore trovato e CORRETTO nella stessa sessione: nello scenario di anticipo orario, `reconcile_fixture_kickoff_lock` registrava `lock_latched_at` sull'orario originale invece del nuovo kickoff reale (il blocco scattava comunque al momento giusto, ma il timestamp d'audit era impreciso). Fix in `fantasy_turns/rules.py` + nuovo test `test_reconcile_fixture_kickoff_lock_anticipated_kickoff`; suite `fantasy_turns`/`fantasy_lineups` (unit) verde dopo il fix. | ALTA (lettura codice + test esistenti + fix verificato) | IMPLEMENTED_VERIFIED |
| EP06-04 | M2 — Ready | Must | Panchina e ordine sostituzioni | EP06, Backend, Frontend, QA | Commit storici squashati (M1: 6d7ec0e, b343888, 460339d, 7850b68; M2: afd3815) senza codice per singola card; modulo corrispondente presente in backend/src, apps/web/src, apps/mobile/src | MEDIA (modulo presente, nessuna prova puntuale) | EVIDENCE_TEMPLATE |
| EP06-05 | M2 — Ready | Must | Tre mosse tattiche | EP06, Backend, Frontend, QA | VERIFICATO B1 (24/09/2026): `MAX_TACTICAL_MOVES=3` in `fantasy_lineups/rules.py::evaluate_tactical_move`, imposto server-side (`assert_tactical_move` solleva `ValidationAuthError` con `tactical_moves_exhausted`). Formazione iniziale e ri-salvataggi identici non consumano mosse; finestra tattica attiva solo con almeno un atleta bloccato. Test: unit `test_tactical_moves_cap_and_window`, `test_tactical_move_after_simultaneous_kickoffs_in_timezones`; integrazione `test_fourth_tactical_move_is_rejected_and_locked_players_stay_frozen`. | ALTA (lettura codice + test esistenti) | IMPLEMENTED_VERIFIED |
| EP06-06 | M2 — Ready | Must | Formazione precedente e bozze | EP06, Backend, Frontend, QA | VERIFICATO B1 (24/09/2026): `LineupDraft` (modello dedicato) + `fallback_service.py`, catena di priorità esplicita alla chiusura turno: bozza salvata e rivalidata → ultima formazione valida di un turno precedente, rivalidata → formazione vuota (0 punti). Applicata solo a turno concluso (`evaluate_round_readiness(...).all_fixtures_finished`), mai a metà turno. Copertura di test forte: `test_resolves_from_a_valid_draft`, `test_falls_through_from_an_incomplete_draft_to_zero`, `test_resolves_from_the_previous_round_when_there_is_no_draft`, `test_falls_to_zero_when_no_draft_and_no_previous_lineup_exist`. | ALTA (lettura codice + test esistenti) | IMPLEMENTED_VERIFIED |
| EP06-07 | M2 — Ready | Must | Rinvii e variazioni orario | EP06, Backend, Frontend, QA | VERIFICATO B1 (24/09/2026): `fantasy_turns/rules.py::reconcile_fixture_kickoff_lock` + `apply_cutoff_recalculation` gestiscono rinvio/anticipo con latch: il cutoff può muoversi prima liberamente ma mai indietro dopo essere scaduto, e un posticipo comunicato dopo l'orario originale non riapre la finestra di modifica. Coperto da test dedicati (`test_reconcile_fixture_kickoff_lock_latches_after_elapsed_not_before`, `test_reconcile_fixture_kickoff_lock_time_shift_without_pst`). Manca un test esplicito per il caso di anticipo orario (vedi nota in EP06-03). | ALTA (lettura codice + test esistenti) | IMPLEMENTED_VERIFIED |
| EP07-01 | M3 — Ready | Must | Formula Rating versionata | EP07, Backend, Database, QA | afd3815 M2 + M3-1 (commit di milestone, non granulare per questa card) | MEDIA (commit di milestone, non per card) | EVIDENCE_TEMPLATE |
| EP07-02 | M3 — Ready | Must | Soglia minuti e senza voto | EP07, Backend, Database, QA | VERIFICATO B4/OQ-07 (24/09/2026) con payload reali, non solo commit: `fantasy_ratings/eligibility.py` gestisce correttamente soglia 15', ingresso in recupero (`is_second_half_stoppage`) ed evento rilevante sotto soglia. Validato su 10 ingressi reali al 90+ trovati nel corpus offline (`minutes` sempre 1, mai proporzionale) — test dedicato `test_real_stoppage_entrants_get_a_small_nonzero_minutes_value`. Chiude anche OQ-07 in `docs/data/api_football_open_questions.md`. | ALTA (payload reali del provider, non sintetici) | IMPLEMENTED_VERIFIED |
| EP07-03 | M3 — Ready | Must | Bonus e malus | EP07, Backend, Database, QA | VERIFICATO B4/OQ-13 (25/09/2026): `bonus.py::compute_bonus_malus` validato contro caso reale del corpus (Reims 2-0 Lille) per la porta inviolata; regola derivata dal punteggio reale della fixture, non dal campo grezzo per-giocatore. Test esistenti: `test_goalkeeper_clean_sheet_bonus`, `test_goalkeeper_goals_conceded_malus`, `test_penalty_saved_bonus_only_for_goalkeeper`, `test_goals_conceded_not_applied_outside_goalkeeper_role`, `test_pending_score_skips_goalkeeper_components`. | ALTA (commit dedicato + payload reale + test esistenti) | IMPLEMENTED_VERIFIED |
| EP07-04 | M3 — Ready | Must | Sostituzioni e formazione effettiva | EP07, Backend, Database, QA | 7024a9f EP07-04: sostituzioni automatiche e formazione effettiva (FR-SUB-01) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP07-05 | M3 — Ready | Must | Punteggio, fasce gol e scontro diretto | EP07, Backend, Database, QA | VERIFICATO B2 (24/09/2026): backend persiste due grandezze distinte per slot H2H (`homeScore`/`awayScore` = Punti, somma fantavoti undici effettivi; `homeFantasyGoals`/`awayFantasyGoals` = Gol fantasy, conversione a soglie in `docs/api/league_scoring.md`). Client (web e mobile, stesso pacchetto `@fantappero/contracts/h2hScore.ts`) mostra le due righe etichettate separatamente ("Punti"/"Gol fantasy"), mai un numero anonimo tra parentesi — copre esplicitamente l'esempio del piano (72,5 (2) – 68 (1) da evitare). | ALTA (lettura codice condiviso web+mobile) | IMPLEMENTED_VERIFIED |
| EP07-06 | M3 — Ready | Must | Classifica e criteri di parità | EP07, Backend, Database, QA | 47e852c, f424dd8 EP07-06: classifica e criteri di parita, collegata | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP07-07 | M3 — Ready | Must | Correzioni, ricalcolo e omologazione | EP07, Backend, Database, QA | VERIFICATO B2 (24/09/2026): `fantasy_turns/homologation_service.py` (FR-OMO-01) — un turno omologato non cambia più per nuove versioni della formula; solo una correzione esplicita con permesso, motivo e traccia in audit (`LeagueAuditEvent`, azioni `FANTASY_ROUND_HOMOLOGATED`/`FANTASY_ROUND_CORRECTION_APPLIED`) può riaprirlo per ricalcolo. Test: unit `test_homologation.py`, integrazione `test_round_calculation_service.py`, `test_scoring_service.py`, `test_homologation_notifications.py`. | ALTA (lettura codice + test esistenti) | IMPLEMENTED_VERIFIED |
| EP08-01 | M3 — Ready | Must | Sessione asta a buste | EP08, Backend, Frontend, Database, QA | f36d69f, 033d298 EP08-01: sessione asta a buste, collegata a API reali | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP08-02 | M3 — Ready | Must | Risoluzione buste e parità | EP08, Backend, Frontend, Database, QA | 044d870, 033d298 EP08-02: risoluzione buste e parita | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP08-03 | M3 — Ready | Must | Svincolati con giocatore da tagliare | EP08, Backend, Frontend, Database, QA | 52ccb4c, 5a7c84a EP08-03: svincolati con giocatore da tagliare | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP08-04 | M3 — Ready | Must | Recupero crediti allo svincolo | EP08, Backend, Frontend, Database, QA | 542cde6, 999b8c4 EP08-04: recupero crediti allo svincolo | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP08-05 | M3 — Ready | Should | Proposta di scambio | EP08, Backend, Frontend, Database, QA | b8376c0, cae0d7a EP08-05: proposta di scambio | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP08-06 | M3 — Ready | Should | Accetta, rifiuta e controproponi | EP08, Backend, Frontend, Database, QA | 9830de0, cae0d7a EP08-06: accetta rifiuta controproponi | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP08-07 | M3 — Ready | Must | Approvazione amministratore e limiti | EP08, Backend, Frontend, Database, QA | f4c02af, bfd90e0 EP08-07: approvazione amministratore e limiti | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP08-08 | M3 — Ready | Must | Storico mercato | EP08, Backend, Frontend, Database, QA | 82c79d9, 406425e EP08-08: storico mercato filtrabile | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP09-01 | M4 — Ready | Must | Centro notifiche in-app | EP09, Backend, Frontend, Infrastructure | b287f79 EP09-01: centro notifiche in-app | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP09-02 | M4 — Ready | Must | Reminder kickoff e formazione | EP09, Backend, Frontend, Infrastructure | 3089836 EP09-02: reminder scadenza formazione | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP09-03 | M4 — Ready | Must | Eventi mercato e risultati | EP09, Backend, Frontend, Infrastructure | afb8200 EP09-03: notifiche eventi mercato e risultati | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP09-04 | M4 — Ready | Must | Aggiornamento live client | EP09, Backend, Frontend, Infrastructure | c336d98 EP09-04: aggiornamento live client turni | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP09-05 | M4 — Ready | Should | Canali push/email | EP09, Backend, Frontend, Infrastructure | 262c8a5 EP09-05: canali push e email per le notifiche | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP10-01 | M4 — Ready | Should | Feature store applicativo | EP10, AI, Backend, Frontend | 408f66b EP10-01: feature store applicativo | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP10-02 | M4 — Ready | Should | Viceallenatore | EP10, AI, Backend, Frontend | 63856b2 EP10-02..05: viceallenatore osservatore analista limiti (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP10-03 | M4 — Ready | Should | Osservatore | EP10, AI, Backend, Frontend | 63856b2 EP10-02..05: vedi EP10-02 (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP10-04 | M4 — Ready | Should | Analista | EP10, AI, Backend, Frontend | 63856b2 EP10-02..05: vedi EP10-02 (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP10-05 | M4 — Ready | Should | Limiti, costi e feedback | EP10, AI, Backend, Frontend | 63856b2 EP10-02..05: vedi EP10-02 (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP11-01 | M4 — Ready | Should | Entitlement Gratis e Pro | EP11, Backend, Frontend, Infrastructure | 6b8a512 EP11-01..02: entitlement Gratis Pro e abbonamento personale (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP11-02 | M4 — Ready | Should | Abbonamento personale | EP11, Backend, Frontend, Infrastructure | 6b8a512 EP11-01..02: vedi EP11-01 (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP11-03 | M4 — Ready | Should | Audit log consultabile | EP11, Backend, Frontend, Infrastructure | 2bcd19d EP11-03..05: audit log pannello operatore lega Pro (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP11-04 | M4 — Ready | Should | Pannello operatore | EP11, Backend, Frontend, Infrastructure | 2bcd19d, a857344 EP11-04: pannello operatore, gate reale amministrativo | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP11-05 | M4 — Ready | Should | Lega Pro essenziale | EP11, Backend, Frontend, Infrastructure | 2bcd19d EP11-03..05: vedi EP11-03 (commit unico) | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP12-01 | M5 — Ready | Must | Suite end-to-end critica | EP12, QA, Backend, Frontend, Infrastructure | b2f0a9a EP12-01: suite E2E critica Playwright piu seed scenario. VERIFICATO in questa sessione: `.github/workflows/ci.yml` marca il job `e2e-critical-flow` come "informative", NON obbligatorio per il merge; copre solo 2 flussi (`critical-flow-states`, `registration-to-league`), solo web/Playwright; nessun E2E mobile esiste. | ALTA (verifica diretta CI + codice) | MVP_REMEDIATION |
| EP12-02 | M5 — Ready | Must | Test proprietà e concorrenza | EP12, QA, Backend, Frontend, Infrastructure | e33444d EP12-02: test di proprieta e concorrenza ledger formazioni. VERIFICATO in questa sessione (Blocco B5) sui 4 scenari critici: waiver e approvazione admin trade confermati protetti dal lock già esistente con test diretti aggiunti; omologazione/ricalcolo già testata; salvataggio formazione durante un aggiornamento kickoff concorrente aveva invece una vera finestra di corsa (nessun lock condiviso tra `fixtures` e il salvataggio) — bug reale trovato con un test dedicato e corretto in `fantasy_lineups/service.py` (lettura della partita ora `for_update=True`, stesso pattern già in uso nel file). | ALTA (verifica diretta + bug reale trovato e corretto) | IMPLEMENTED_VERIFIED |
| EP12-03 | M5 — Ready | Must | Performance e capacità | EP12, QA, Backend, Frontend, Infrastructure | 21d280e EP12-03: performance capacity baseline | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP12-04 | M5 — Ready | Must | Security review | EP12, QA, Backend, Frontend, Infrastructure | bef6875, d34b372 EP12-04: security review CORS DoS dipendenze secret | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP12-05 | M5 — Ready | Must | Backup e disaster recovery | EP12, QA, Backend, Frontend, Infrastructure | d6a61eb EP12-05: backup e disaster recovery | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP12-06 | M5 — Ready | Must | Runbook e supporto pilot | EP12, QA, Backend, Frontend, Infrastructure | 71be8a9 EP12-06: pilot incident runbooks | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP12-07 | M5 — Ready | Must | Pilot e gate Beta chiusa | EP12, QA, Backend, Frontend, Infrastructure | a616930 EP12-07: closed beta pilot gate package | ALTA (commit dedicato) | EVIDENCE_TEMPLATE |
| EP13-P01 | PRE-M5.1 — Ready | - | Navigazione gerarchica “Lega” su web e mobile | UX, Web, Mobile, Autorizzazioni | Nessun commit con codice dedicato. Possibili commit correlati non taggati da verificare: 1079614, a9af666, 892c191, 69612dd, 2a70cf2, 87a8914, fef455d | BASSA (nessun commit dedicato) | EVIDENCE_TEMPLATE |
| EP13-P02 | PRE-M5.1 — Ready | - | Magic Points e Score espliciti nei turni fantallenatori | Turni, H2H, Scoring, Web, Mobile | VERIFICATO B2 (24/09/2026), CORREZIONE alla stima automatica: implementata, nonostante nessun commit dedicato individuato in git log. `packages/contracts/src/h2hScore.ts` cita esplicitamente "EP13-P02" nel proprio docstring e implementa "Punti"/"Gol fantasy" come righe etichettate separate, riusate identiche da `apps/web/src/pages/MatchdayH2HPanel.tsx` e `apps/mobile/src/screens/matchday/MatchdayH2HPanel.tsx`. Conferma che la cronologia squashata nasconde lavoro reale anche per le card Pre-M5.1, non solo per M1/M2. | ALTA (codice condiviso con riferimento esplicito al codice card) | IMPLEMENTED_VERIFIED |
| EP13-P03 | PRE-M5.1 — Ready | - | Calendario H2H adattivo sui turni europei eleggibili | Calendario, Turni, H2H, Backend, Web, Mobile | VERIFICATO B3 (24/09/2026, SOLO LETTURA), CORREZIONE alla stima automatica: implementata nonostante nessun commit dedicato trovato. `assert_plan_invariants` cita esplicitamente "EP13-P03" nel proprio docstring. Corrispondenza 1:1 giornata H2H ↔ finestra Turno Europeo eleggibile; `sync_with_european_turns`/`extend_to_european_turns`/`realign_round_numbers` in `calendar_service.py` gestiscono rigenerazione idempotente e **conservano le giornate già disputate** (estendono in coda invece di rigenerare se esistono già risultati calcolati) — con un bug di rinumerazione documentato e già risolto nel codice stesso (vedi docstring di `realign_round_numbers`). Terza card Pre-M5.1 su tre controllate finora risultata implementata pur senza commit dedicato: la confidenza BASSA automatica per l'intero gruppo Pre-M5.1 era sistematicamente troppo pessimista. | ALTA (lettura codice + test esistenti, nessuna modifica) | IMPLEMENTED_VERIFIED |
| EP13-P04 | PRE-M5.1 — Ready | - | Turni europei live con risultati, formazioni ed eventi | Live, Provider, Turni, Web, Mobile, Observability | Nessun commit con codice dedicato. Possibili commit correlati non taggati da verificare: 1079614, a9af666, 892c191, 69612dd, 2a70cf2, 87a8914, fef455d | BASSA (nessun commit dedicato) | EVIDENCE_TEMPLATE |
| EP13-P05 | PRE-M5.1 — Ready | - | Formazione automatica dei fantallenatori IA | IA, Formazioni, Provider, Fairness, Backend, Mobile | Nessun commit con codice dedicato. Possibili commit correlati non taggati da verificare: 1079614, a9af666, 892c191, 69612dd, 2a70cf2, 87a8914, fef455d | BASSA (nessun commit dedicato) | EVIDENCE_TEMPLATE |
| EP13-P06 | PRE-M5.1 — Ready | - | Preview e profilo storico dei fantallenatori | Fantallenatori, Profilo, Privacy, Web, Mobile | Nessun commit con codice dedicato. Possibili commit correlati non taggati da verificare: 1079614, a9af666, 892c191, 69612dd, 2a70cf2, 87a8914, fef455d | BASSA (nessun commit dedicato) | EVIDENCE_TEMPLATE |
| EP13-P07 | PRE-M5.1 — Ready | - | Notifica e badge rosso per gli inviti pendenti | Inviti, Notifiche, Badge, Web, Mobile | Nessun commit con codice dedicato. Possibili commit correlati non taggati da verificare: 1079614, a9af666, 892c191, 69612dd, 2a70cf2, 87a8914, fef455d | BASSA (nessun commit dedicato) | EVIDENCE_TEMPLATE |
| EP13-F01 | Fase 2 — Discovery | - | Discovery Fase 2 — club/formazione personale prima della lega | Discovery, Product, DataModel, Web, Mobile | Card etichettata Fase 2 - Discovery nel CSV sorgente | ALTA (dichiarata dalla fonte) | PHASE2_BACKLOG |
| EP13-01 | M5.1 — Chiusura Beta e Pilot reale | Must | Freeze della release candidate multipiattaforma | EP13, QA, Backend, Frontend, Mobile, Infrastructure | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-02 | M5.1 — Chiusura Beta e Pilot reale | Must | Inventario normativo e registro di tracciabilità totale | EP13, Product, Documentation, QA, Backend, Frontend, Mobile | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-03 | M5.1 — Chiusura Beta e Pilot reale | Must | Chiusura atomica di tutti i gap MVP documentati | EP13, QA, Backend, Frontend, Mobile, Product | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-04 | M5.1 — Chiusura Beta e Pilot reale | Must | Parità funzionale web/mobile e E2E su dispositivo | EP13, Mobile, Frontend, Backend, QA, UX | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-05 | M5.1 — Chiusura Beta e Pilot reale | Must | Performance e osservabilità della candidata web/mobile | EP13, QA, Backend, Mobile, Infrastructure, Observability | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-06 | M5.1 — Chiusura Beta e Pilot reale | Must | Rivalidazione sicurezza pre-pilot multipiattaforma | EP13, Security, Backend, Frontend, Mobile, Infrastructure | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-07 | M5.1 — Chiusura Beta e Pilot reale | Must | Ambiente pilot, backup offsite e cutover DR | EP13, Infrastructure, Operations, Security, Database, Mobile | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-08 | M5.1 — Chiusura Beta e Pilot reale | Must | Governance, privacy e supporto del pilot | EP13, Product, Operations, Security, Privacy, Mobile | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-09 | M5.1 — Chiusura Beta e Pilot reale | Must | Selezione, onboarding e smoke web/mobile delle leghe pilota | EP13, Operations, Product, Infrastructure, QA, Mobile | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-10 | M5.1 — Chiusura Beta e Pilot reale | Must | Esecuzione del pilot reale e raccolta KPI multipiattaforma | EP13, Operations, QA, Infrastructure, Pilot, Mobile | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-11 | M5.1 — Chiusura Beta e Pilot reale | Must | Gate firmato GO/NO-GO e remediation | EP13, Product, Operations, Security, Infrastructure, Gate, Mobile | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |
| EP13-12 | M5.1 — Chiusura Beta e Pilot reale | Should | Backlog Fase 2 completo da tutte le fonti | EP13, Product, UX, Backend, Frontend, Mobile, Infrastructure | Nessun commit trovato: card non ancora iniziata, appartiene al pacchetto M5.1 oggetto di questo piano di chiusura | ALTA (assenza confermata) | MVP_REMEDIATION |

## 6. Prossimi passi per chiudere davvero EP13-02

1. Per ogni riga `EVIDENCE_TEMPLATE` con confidenza ALTA (M3–M5, 34 card): verifica rapida — eseguire il test/E2E collegato e allegare l'esito, poi riclassificare in `IMPLEMENTED_VERIFIED` o `MVP_REMEDIATION`.
2. Per le righe con confidenza MEDIA (M0.5–M2, 38 card): serve ispezione puntuale del codice per card (non solo del modulo), perché la cronologia squashata non distingue le singole card.
3. Per le 7 card Pre-M5.1 (confidenza BASSA): verificare manualmente se i commit correlati elencati coprono davvero la card, oppure se il lavoro non è mai partito.
4. Aggiungere al registro le fonti non-card richieste da EP13-02: le 9 open question API-Football, i debiti tecnici dichiarati in `docs/adr/`, i vincoli privacy/security, e i documenti `.docx/.pdf` in `docs/doc_fantapperò/` non ancora incrociati riga per riga.
5. Assegnare un owner reale a ogni riga (oggi assente per tutte).

## 7. Log di verifica — Blocco B

### B1 — Lock individuale dopo variazione kickoff (24/09/2026)

Verificato lo scenario guida del piano (partita spostata da 20:45 a 18:30, un utente non deve poter modificare alle 19:00 un calciatore già sceso in campo):

- **Comportamento confermato corretto**: il lock è calcolato server-side per singolo atleta (`fantasy_lineups/rules.py::is_athlete_kickoff_locked`) dal `kickoff_at` corrente della fixture, ricalcolato ad ogni richiesta (`_sync_round_kickoffs` → `fantasy_turns/service.py::_reconcile_cutoff`). Il salvataggio formazione rifiuta con eccezione reale (`ValidationAuthError` via `assert_progressive_lock`/`assert_bench_order_lock`) se si tocca uno slot di un atleta bloccato — non è un controllo solo lato UI.
- **`apply_cutoff_recalculation`**: il cutoff di turno può anticipare liberamente ma non torna mai indietro dopo essere scaduto; un posticipo comunicato tardi non riapre la finestra.
- **Difetto minore trovato e corretto**: nel caso di anticipo orario, `lock_latched_at` registrava il vecchio orario pubblicato invece del nuovo kickoff reale (il blocco scattava comunque al momento giusto, ma il timestamp d'audit era impreciso). Corretto in `fantasy_turns/rules.py::reconcile_fixture_kickoff_lock` (usa l'istante scaduto più vicino tra osservato e corrente, non il primo non nullo). Aggiunto test `test_reconcile_fixture_kickoff_lock_anticipated_kickoff`. Suite `fantasy_turns`/`fantasy_lineups` (unit, 96 test) verde dopo il fix.
- Righe registro aggiornate: `EP06-03`, `EP06-07` → `IMPLEMENTED_VERIFIED`.

### B1 — Pannello qualità dati, mosse tattiche, formazione precedente/bozze (24/09/2026)

- **EP04-07 (pannello qualità dati)**: modulo reale `sports_data/quality/` (rules/service/router/tasks) con rilevamento anomalie (mancanti, in ritardo, in conflitto, corrette) e retry, test unit+integrazione. Copre la qualità operativa della sincronizzazione dati, non sostituisce le 9 domande normative aperte di B4.
- **EP06-05 (tre mosse tattiche)**: limite di 3 mosse imposto server-side con eccezione reale, formazione iniziale e ri-salvataggi identici esclusi dal conteggio, ampia copertura di test incluso il caso limite (quarta mossa rifiutata) e kickoff simultanei in fusi orari diversi.
- **EP06-06 (formazione precedente e bozze)**: catena di fallback esplicita e testata (bozza rivalidata → formazione turno precedente rivalidata → vuota/0 punti), applicata solo a turno concluso per non togliere tempo utile al fantallenatore.
- Righe registro aggiornate: `EP04-07`, `EP06-05`, `EP06-06` → `IMPLEMENTED_VERIFIED`.
- **Blocco B1 così completato** per tutti i 7 punti elencati dal piano (pannello qualità dati, mosse tattiche, recupero formazione precedente, bozze, rinvii/cambi orario, lock individuale, rifiuto server-side — quest'ultimo confermato di riflesso dalle eccezioni osservate in tutti i punti sopra).

### B2 — Flusso risultati reale (24/09/2026)

Verificato lo stato del tab "Risultati" (Matchday H2H), che una documentazione E2E precedente descriveva come statico/seed-driven:

- **Dati reali, non statici**: `apps/web/src/pages/MatchdayPage.tsx` chiama API autenticate reali (`fetchH2HCalendar`, `fetchFantasyTurn`, `fetchFantasyTurns`), nessun dato hardcoded.
- **Distinzione Punti/Gol fantasy esplicita**: `packages/contracts/src/h2hScore.ts` (condiviso web+mobile) persiste e mostra due grandezze separate ed etichettate ("Punti" = somma fantavoti; "Gol fantasy" = conversione a soglie), mai un numero anonimo tra parentesi — copre esattamente l'esempio del piano da evitare (`72,5 (2) – 68 (1)`).
- **Tre stati distinti**: per-scontro `pending`/`provisional`/`final` (`H2HResultStatus`); a livello di turno `homologationStatus` separato (es. `homologated`), coerente con "provvisorio, finale e omologato" richiesto dal piano.
- **Correzioni auditate**: `homologation_service.py` — un turno omologato non cambia per nuove versioni della formula; solo una correzione esplicita (permesso, motivo, `LeagueAuditEvent`) può riaprirlo per ricalcolo.
- **Parità web/mobile confermata**: stesso modulo contratti riusato identico da `apps/mobile/src/screens/matchday/MatchdayH2HPanel.tsx`.
- **Scoperta rilevante**: `EP13-P02` (Pre-M5.1, "Magic Points e Score espliciti") risulta implementata nonostante nessun commit dedicato trovato in git log — la stima automatica di confidenza BASSA per le card Pre-M5.1 era troppo pessimista. Da ripetere il controllo puntuale per le altre 6 card Pre-M5.1 prima di darle per non fatte.
- Righe registro aggiornate: `EP07-05`, `EP07-07`, `EP13-P02` → `IMPLEMENTED_VERIFIED`.
- **Non ancora verificato in B2**: comportamento preciso del ricalcolo dopo una correzione tardiva del provider dati (il meccanismo di audit esiste, ma non è stato ancora provato un caso reale end-to-end di correzione post-omologazione).

### B3 — Calendario H2H e turni europei (24/09/2026, SOLO LETTURA)

Su richiesta esplicita, questa verifica è stata condotta **senza modificare alcun file** in quest'area (lavoro pregresso significativo già investito dal team su calendario/turni europei).

- **Cicli completi, nessun duplicato, bye equo, alternanza casa/trasferta**: tutti verificati da `assert_plan_invariants` (`leagues/calendar_planning.py`), eseguito anche in produzione (`calendar_service.py:170`), non solo nei test. Bilanciamento casa/trasferta con decomposizione euleriana (risolve un ottimo locale del greedy precedente, documentato per 7 partecipanti).
- **Copertura test oltre il richiesto**: parametrizzata su **4-10 partecipanti** (il piano ne chiedeva 4/5/8/10).
- **Mapping giornata H2H ↔ finestra europea**: corrispondenza 1:1 esplicita e verificata (`seen_windows`, ordine cronologico).
- **Rigenerazione idempotente e conservazione giornate già iniziate**: `sync_with_european_turns` sceglie l'azione meno distruttiva — rigenera solo se non esistono ancora risultati calcolati, altrimenti estende in coda preservando gli scontri già disputati. Un calendario già pubblicato resta pubblicato dopo rigenerazione.
- **Qualità del codice**: un bug reale di rinumerazione giornate (non allineamento fra numeri H2H e Turni Europei) risulta già trovato e risolto dal team stesso, documentato nel docstring di `realign_round_numbers` — segno di un modulo maturo e già passato da un ciclo di hardening.
- **Terza conferma della stessa scoperta di B2**: anche `EP13-P03` (Pre-M5.1) risulta implementata pur senza commit dedicato in git log — tre card Pre-M5.1 su tre controllate finora erano tutte in realtà già fatte. La confidenza BASSA automatica assegnata all'intero gruppo Pre-M5.1 nella bozza iniziale era sistematicamente troppo pessimista; le 4 card Pre-M5.1 rimanenti (P01, P04, P06, P07) vanno ricontrollate prima di darle per non fatte.
- Righe registro aggiornate: `EP03-06`, `EP13-P03` → `IMPLEMENTED_VERIFIED`.
- **Non verificato in B3** (fuori dallo scope di sola lettura richiesto, o non controllato): comportamento con fixture sospese durante il turno (solo il caso "cancellate" è coperto da test), sincronizzazione con partite realmente rinviate su un turno già in corso.

### B4 — Domande aperte sui dati API-Football (24/09/2026)

A differenza di B1-B3, qui non si tratta di verificare codice esistente ma di valutare decisioni normative ancora aperte (9 domande, `docs/data/api_football_open_questions.md`, OQ-07…OQ-15). Non ho inventato risposte: ho verificato cosa esiste davvero come base per chiuderle.

- **Corpus di evidenza reale già presente**: `backend/tests/fixtures/api_football/manifest.json` (creato 2026-07-27) — 20 fixture FT reali sui 5 campionati richiesti (39/140/135/78/61), con casi rari già taggati (`clean_sheet`, `own_goal`, `penalty_missed/saved/scored`, `red_card`, `substitution`). È il materiale grezzo che la checklist EP00-02 richiede.
- **Due endpoint mai acquisiti**: `/injuries`, `/predictions`, `/standings` — senza questi dati **OQ-11 e OQ-14 non sono chiudibili** con il corpus attuale; serve una nuova acquisizione con chiave provider reale (fuori portata di un'analisi di solo codice).
- **Due casi rari cercati ma non trovati nel corpus**: `post_match_correction`, `postponement` — le regole esistono e sono testate con dati sintetici (B1/B3), ma manca ancora una prova su payload reale.
- **Gap più rilevante trovato**: il corpus non è collegato ai test delle regole di dominio. `test_sports_dataset.py` valida solo integrità/checksum del corpus, nessun test fa girare `fantasy_ratings/bonus.py`/`eligibility.py` sui payload reali per produrre l'evidenza Pass/Fail richiesta da EP00-02. Il materiale c'è, il collaudo descritto nella checklist non risulta eseguito.
- **OQ-15 (ID leghe/season) parzialmente chiudibile subito**: `MVP_LEAGUE_IDS = (39, 140, 135, 78, 61)` è una config versionata unica, riusata coerentemente in tutto `sports_data/`. La parte su `season` corrente resta invece per-lega, non una costante piattaforma — nessuna evidenza su verifica del delay di popolazione fixture a inizio stagione.
- Aggiornato `docs/data/api_football_open_questions.md` con nota di stato ed esito parziale OQ-15.
- **Deliberatamente non chiuse a questo punto**: OQ-08, OQ-09, OQ-10, OQ-11, OQ-12, OQ-13, OQ-14. OQ-09 in particolare è esplicitamente una decisione di prodotto ("non inventare pesi qui" nel testo originale del documento), non qualcosa che un'analisi di codice possa risolvere da sola.

### B4 (continua) — OQ-07 chiusa con prova reale (24/09/2026)

Su richiesta dell'utente di affrontare le domande aperte una per una, a partire dalla prima (OQ-07 — minuti, recupero, senza voto):

- Scritto un test che usa i payload **reali** del corpus offline (non sintetici) per validare `fantasy_ratings/eligibility.py` contro tutte le 20 fixture disponibili.
- Trovati **10 ingressi reali in recupero del secondo tempo** nel corpus; in tutti i casi il provider riporta `minutes: 1` — mai 0, mai proporzionale al recupero realmente giocato. Risposta empirica e concreta alla domanda originale.
- Confermato che la regola già in codice gestisce correttamente questo caso (non si fida della sola soglia minuti per chi entra in recupero, richiede un evento rilevante).
- **OQ-07 chiusa** in `docs/data/api_football_open_questions.md`. `EP07-02` → `IMPLEMENTED_VERIFIED`.
- Alla scrittura di questa nota risultava non risolto il caso "giocatori convocati in panchina ma mai entrati" — **risolto poco dopo durante OQ-08** (vedi sotto): compaiono sì nel payload stats, con `games.minutes`/`games.rating` null e `games.substitute: true`.

### B4 (continua) — OQ-08 chiusa parzialmente con prova reale (24/09/2026)

- Calcolata una tabella % null reale (non stimata) sui campi che la formula v1 bonus/malus consuma oggi, su 694 entry giocatore-partita del corpus, tutti e 5 i campionati: `goals.total` 91-94% null, `goals.assists` 57-98%, `penalty.saved` 93-95%, `cards.red`/`cards.yellow`/`penalty.missed` ~0%, `games.minutes`/`games.rating` 8-22%.
- **Verificato che gli alti tassi di null sui campi di conteggio non sono un problema**: il provider usa `null` per "zero occorrenze" (la maggior parte dei giocatori non segna/assiste/para un rigore), e `fantasy_ratings/input.py::_as_int` già tratta `None` come 0 correttamente.
- **`goals.conceded` (nullo 0-43% a seconda della lega) non è nemmeno usato dal codice**: la porta inviolata viene calcolata da `mapping.py::team_goals_conceded` leggendo il punteggio reale della fixture, non il campo grezzo per-giocatore — il problema di coverage era quindi già aggirato dal design, non solo tollerato.
- **Unico null "vero" trovato**: `games.minutes`/`games.rating`, ed è sempre e solo per convocati in panchina mai entrati (`games.substitute: true`) — verificato senza eccezioni su tutto il corpus. Questo chiude anche il dubbio residuo lasciato aperto da OQ-07.
- Test aggiunti: `backend/tests/unit/fantasy_ratings/test_real_corpus_coverage.py` (4 test, tutti sui payload reali).
- **OQ-08 chiusa parzialmente** in `docs/data/api_football_open_questions.md`: chiusa per i campi già usati dalla formula v1, resta aperta la lista completa di campi (saves, shots, passes, tackles, duels, fouls) per la futura Rating Beta, che dipende dalla decisione di prodotto OQ-09.
- **OQ-08 (parte residua) e OQ-09 messe in coda su richiesta esplicita** — da riprendere più avanti, non abbandonate.

### B4 (continua) — OQ-10 chiusa parzialmente (25/09/2026)

- **Caso reale trovato nel corpus**: fixture 37834, giocatore 68091 — ha giocato 90 minuti interi (rating reale 6.9) ma è **assente dalla lineup ufficiale** di quella partita. Conferma diretta e concreta che "presente nelle stats ma non nella lineup" è un caso reale, non teorico.
- **Buona notizia**: lo scoring non dipende affatto dalla lineup ufficiale — legge direttamente l'endpoint statistiche giocatore — quindi questo tipo di lacuna non tocca il fantavoto.
- **L'eccezione admin richiesta dal criterio di chiusura esiste già**, ma solo per l'assenza *totale* di lineup su una partita conclusa: il pannello qualità dati (verificato in B1) la segnala come warning.
- **Zona non coperta**: la formazione automatica IA (EP13-P05) usa la lineup ufficiale per decidere chi schierare pre-partita, e ha un percorso "incompleto" già previsto per i dati parziali — ma non ho verificato la qualità di quel fallback nel caso specifico di lineup presente-ma-sbagliata come quello trovato nel corpus (solo per lineup del tutto assente).
- **Non risolvibile da qui**: nessuna policy booleana esplicita "was_called_up" nel codice; il tempo medio di pubblicazione della lineup prima del calcio d'inizio per campionato richiede dati di monitoraggio in produzione su partite live, non ricavabile da un corpus statico post-partita.
- Aggiornato `docs/data/api_football_open_questions.md` (OQ-10, esito parziale). Nessuna riga di registro EP aggiornata: la card più vicina (EP04-06 scheduler) non è stata verificata nel suo complesso, solo questo aspetto specifico.
- **Parte IA (fallback su lineup presente-ma-sbagliata) messa in coda** su richiesta esplicita.

### B4 (continua) — OQ-11 bloccata, confermato il gap (25/09/2026)

- **Confermato con certezza (non solo sospetto)**: `/injuries` non è mai chiamato dal codice. Unici riferimenti: un elenco statico in `provider/constants.py` e un flag di sola copertura dichiarata (non dati reali) in `provider/mapping.py`.
- **L'unico segnale realmente sincronizzato** è `Athlete.injured`, un booleano grezzo — lo stesso che la documentazione interna già segnala come "non affidabile da solo".
- Nessun enum Injury/Suspension, nessun campo `reason`, nessuna integrazione `/sidelined`.
- Il corpus offline non aiuta: `/injuries` non è mai stato scaricato in nessuna delle 20 fixture.
- **OQ-11 non è chiudibile da un'analisi di solo codice**: serve una nuova raccolta dati con chiave provider reale, oppure una decisione esplicita del team su come trattare il solo booleano `injured` come rischio accettato nel frattempo.
- Aggiornato `docs/data/api_football_open_questions.md` (OQ-11, bloccata). Nessuna riga di registro EP toccata: non c'è nulla da verificare come "fatto", il gap è reale e confermato.

### B4 (continua) — OQ-11: chiamate reali, gap riprodotto, funzionalità implementata (25/09/2026)

Su richiesta esplicita dell'utente, che ha confermato l'esistenza di una chiave API-Football reale già configurata in locale: sbloccata l'indagine con chiamate vere, poi implementata la funzionalità mancante.

- **Chiamata reale a `/injuries`** (Premier League 2024, 3168 voci): confermato che `type` ha solo due valori (`Missing Fixture`, `Questionable`), non Injury/Suspension come presupposto dalla domanda originale. `reason` è un insieme chiuso di 41 valori osservati, non testo libero.
- **Test mirato su richiesta dell'utente** (Lazio, stagione 2026, confronto con una fonte di riferimento nota): 4 giocatori su 5 trovati, **1 mancante del tutto** (Filipe Bordon) — confermato anche cercandolo per ID diretto su due stagioni, zero risultati. Riproduce concretamente il sospetto dell'utente su un bug reale del provider.
- **Decisa e implementata la policy conseguente**: l'assenza di un record non deve mai essere letta come "disponibile" — solo come "sconosciuto".
- **Nuova funzionalità realizzata** (non solo documentazione): modulo `backend/src/sports_data/availability/` (`models.py`, `classify.py`, `sync.py`), enum `PlayerAvailabilityCategory` in `database/enums.py`, migrazione Alembic `2fb4800de433` (verificata up/down/drift-check su database isolato via Docker), test unit (`test_availability_classify.py`) e integrazione (`test_availability_sync.py`).
- **Deliberatamente non collegato** a `fantasy_ratings/eligibility.py` o alla selezione formazione IA — la sincronizzazione e la lettura sicura (`is_confirmed_unavailable`) sono pronte, il collegamento ai consumatori resta un passo successivo esplicito, per non allargare lo scope di questa card.
- Corretto anche un piccolo problema trovato per strada: `backend/tests/integration/database/test_migrations.py` aveva l'head Alembic atteso hardcoded (rotto da ogni nuova migrazione) — aggiornato alla nuova head.
- **Nota metodologica**: durante la verifica trovato un test pre-esistente e rotto indipendentemente da questo lavoro (`test_a_league_without_rosters_generates_no_turns`, fantasy_turns) — confermato con `git stash` che fallisce anche sulla baseline precedente, non è una regressione introdotta qui. Segnalato, non corretto (fuori scope OQ-11).
- **OQ-11 chiusa** in `docs/data/api_football_open_questions.md`.
- **Prossima in ordine**: OQ-12 (trasferimenti/uscita dai 5 campionati).

## 8. Lavoro pronto ma non ancora collegato (follow-up da riprendere)

Elenco esplicito, separato dal log cronologico, così non si perde tra le date.

### Sync disponibilità giocatori (OQ-11) — manca il collegamento ai consumatori

**Cosa esiste già**, pronto all'uso: `backend/src/sports_data/availability/`
- `sync.py::sync_player_availabilities` — sincronizza `/injuries` in modo idempotente
- `sync.py::is_confirmed_unavailable(session, athlete_provider_id=..., competition_provider_id=..., season_year=...)` — ritorna il record se esiste, altrimenti `None` (= "sconosciuto", mai "disponibile")

**Cosa manca** perché serva davvero a qualcosa:
1. **Un job schedulato** che chiami `sync_player_availabilities` periodicamente (oggi va invocato manualmente/a mano — non è collegato a `sports_data/scheduler/`).
2. **Un punto di consumo reale**. Candidati più probabili, da valutare insieme prima di implementare:
   - `fantasy_lineups/eligibility.py` — per segnalare a un fantallenatore che un giocatore schierato risulta infortunato/squalificato secondo il provider;
   - `fantasy_lineups/ai_service.py` (formazione automatica IA, EP13-P05) — per escludere automaticamente giocatori con indisponibilità confermata dalla selezione IA;
   - il pannello qualità dati (`sports_data/quality/`) — per segnalarlo come informazione, non come blocco automatico.
3. **Nessuna decisione presa** su quale di questi collegare per primo, né su come l'utente/admin dovrebbe vedere l'informazione (badge in UI? avviso admin? esclusione automatica?).

**Perché non l'ho fatto insieme al resto**: collegarlo alla selezione IA o al lock formazione tocca aree del codice più delicate (vedi la cautela già espressa per il Blocco B3 sul calendario) — meglio deciderlo esplicitamente insieme piuttosto che infilarlo di riflesso dentro il lavoro di OQ-11.

### B4 (continua) — OQ-12: regole già decise e implementate, manca solo la visibilità admin (25/09/2026)

Solo indagine, nessuna modifica al codice.

- **La regola "auto vs coda admin" richiesta dal criterio di chiusura esiste già**: `roster/validators.py::transfer_requires_admin_review` marca Loan/N/A come non affidabili, con un commento nel codice che cita esplicitamente OQ-12 — decisione presa in passato, mai marcata come chiusa nel documento.
- **Rilevamento uscita dai 5 campionati corretto per costruzione**: ogni trasferimento disattiva la membership d'origine; se il club di destinazione non è uno dei 5 campionati censiti, semplicemente non esiste nel catalogo — nessun controllo esplicito necessario.
- **`/players/squads` senza `season`**: confermato non essere un limite, è il comportamento per design dell'endpoint (squadra attuale del provider).
- **Gap reale trovato**: `Transfer.requires_admin_review` viene scritto ma **non è mai letto da nessuna API o UI admin** — la "coda" esiste solo come flag silenzioso nel database. Esiste anche un motivo di svincolo dedicato con rimborso 100% (`MarketReleaseReason.LEAGUE_EXIT`), ma va scelto manualmente da chi fa lo svincolo, senza alcun collegamento al rilevamento automatico dei trasferimenti — stesso pattern "azione finale umana" già visto per OQ-11, corretto per design, ma qui manca anche solo il segnale visibile all'admin.
- **OQ-12 chiusa parzialmente** in `docs/data/api_football_open_questions.md`. Nessuna riga di registro EP modificata (la funzionalità di sync trasferimenti è più ampia di questo singolo aspetto).
- **Non implementato** (in attesa di conferma): un endpoint/coda admin che esponga i trasferimenti con `requires_admin_review=true` ancora da valutare.

### B4 (continua) — OQ-12: costruita la coda admin (25/09/2026)

Su richiesta esplicita, implementata la visibilità mancante trovata sopra.

- **Nuovo**: `admin/transfers_service.py` (`AdminTransfersService.list_pending_review`, `.mark_reviewed`), due endpoint in `admin/router.py` (`GET /admin/transfers/pending-review`, `POST /admin/transfers/{id}/review`), entrambi dietro `Permission.GLOBAL_OPERATE`.
- **Colonne aggiunte a `Transfer`**: `reviewed_at`, `reviewed_by_user_id` — migrazione `37c365bf2399`, verificata up/down/drift-check su database isolato (stesso metodo usato per OQ-11).
- **Trovato e corretto un errore nel primo tentativo di migrazione**: `LeagueAuditAction` è un enum nativo PostgreSQL, aggiungere un valore Python non basta — serve `ALTER TYPE ... ADD VALUE` esplicito nella migrazione (il primo giro di test l'ha fatto fallire subito, corretto prima di procedere).
- **Nuova azione di audit**: `ROSTER_TRANSFER_REVIEWED`, registrata su ogni conferma admin con `league_id=None` (evento di piattaforma, non di lega — stesso pattern di `PLATFORM_OPERATOR_PROMOTED`).
- Test: `backend/tests/integration/authorization/test_admin_transfers.py` (5 casi: autenticazione richiesta, accesso negato a non-operatori, comparsa/sparizione dalla coda dopo revisione, doppia revisione rifiutata, ID sconosciuto → 404).
- **Deliberatamente non collegato** al credito 100% (`MarketReleaseReason.LEAGUE_EXIT`): la coda rende visibile *quali* trasferimenti aspettano una decisione, ma l'eventuale svincolo con rimborso resta un'azione separata e manuale — stessa cautela già applicata a OQ-11 (mai automatizzare l'ultimo passo senza una decisione esplicita a parte).
- **OQ-12 ora chiusa per intero** in `docs/data/api_football_open_questions.md`.

### B4 (continua) — OQ-13: porta inviolata, chiusa (25/09/2026)

Solo indagine, nessuna modifica al codice — la regola era già corretta.

- **Regola già ben progettata**: `bonus.py::compute_bonus_malus` non legge il campo grezzo per-giocatore `goals.conceded` (che in B4/OQ-08 avevamo trovato con tasso di null variabile 0-43% per lega); calcola invece i gol subiti dal punteggio reale della fixture (`mapping.py::team_goals_conceded`) — un design più robusto di quanto la domanda originale presupponesse.
- **Validato su un caso reale del corpus**: Reims 2-0 Lille (fixture 157445, tag `clean_sheet`) — conferma che la logica produce il risultato corretto su dati veri, non solo sintetici.
- **Le tre domande hanno risposta concreta dal codice**: (1) non serve arrivare a 90 minuti, basta l'eleggibilità al voto (soglia configurabile); (2) vale per i subentrati, e — comportamento intenzionale coerente con le regole standard del fantacalcio italiano — più portieri della stessa partita possono condividere la porta inviolata se la squadra chiude senza subire; (3) durante una sospensione il bonus può essere calcolato ma resta sempre provvisorio: il turno non viene mai omologato finché la partita non risulta davvero conclusa (`FT`/`AET`/`PEN`).
- **Gap minore, non bloccante**: il caso "due portieri, stessa porta inviolata" non ha un test dedicato — verificato leggendo il codice, non con una prova automatica.
- **OQ-13 chiusa** in `docs/data/api_football_open_questions.md`. `EP07-03` → `IMPLEMENTED_VERIFIED`.
### B4 (continua) — OQ-14: chiamate reali fatte, funzionalità non ancora decisa (25/09/2026)

- **Chiamate reali** a `/predictions` e `/standings` (chiave già configurata): **copertura 100%** su un campione di 17 fixture reali sui 5 campionati (prossimo turno) — entrambi gli endpoint rispondono sempre con dati veri, non solo occasionalmente.
- `/predictions` include probabilità %, previsione vincitore, consiglio testuale; il campo `under_over` è risultato `null` nel campione — da trattare come opzionale.
- **Conferma del gap**: zero righe di codice in `ai_assistant/` consumano questi due endpoint. La policy "mai verità di scoring, solo segnale" è già scritta nella documentazione ma senza alcuna implementazione.
- **Non implementato**: manca ancora una decisione su quali campi esporre allo staff IA e come strutturare lo snapshot richiesto dal criterio di chiusura — a differenza di OQ-11/OQ-12, qui la decisione di scope non è stata ancora presa.
- **OQ-14 chiusa parzialmente** in `docs/data/api_football_open_questions.md` (dati reali verificati, funzionalità da costruire in sospeso).
- **Prossima in ordine tra le domande rimaste**: nessuna — OQ-14 era l'ultima delle nuove. Restano solo le 4 messe in coda (OQ-08 residuo, OQ-09, OQ-10 residuo, OQ-15 residuo).

### B5 — Test di concorrenza sui 4 scenari critici (26/09/2026)

Il piano (EP12-02) chiedeva prove dirette di concorrenza su market/formazioni, non solo l'esistenza di un test generico. Verificati singolarmente i 4 scenari citati dal criterio di chiusura.

- **Kickoff che cambia durante il salvataggio della formazione — BUG REALE TROVATO E CORRETTO.** `save_my_lineup` (`fantasy_lineups/service.py`) leggeva lo stato delle partite una sola volta (`_athlete_kickoffs`) e non lo rileggeva mai prima del commit finale: un aggiornamento concorrente (es. lo scheduler dati sportivi che segna "partita iniziata") poteva intrufolarsi in quella finestra e far passare un salvataggio che avrebbe dovuto essere respinto. Riprodotto con un test che inietta l'aggiornamento concorrente in un punto preciso (non affidato al caso): il salvataggio *non* rifiutava la promozione di un portiere la cui partita era già iniziata.
  - **Corretto su indicazione esplicita dell'utente** (area sensibile, consultazione richiesta prima di ogni modifica): la lettura dello stato delle partite ora blocca a riga (`for_update=True`) le partite coinvolte fino al commit — stesso meccanismo già in uso nello stesso file per il turno e per la formazione salvata. Un aggiornamento concorrente deve aspettare che il salvataggio finisca, non può più intrufolarsi a metà.
  - Il test originale (iniezione sincrona nello stesso thread) sarebbe rimasto in stallo con il lock vero; riscritto per provare direttamente il blocco a livello di database: apre il "salvataggio" senza chiuderlo, tenta una scrittura concorrente con timeout breve e verifica che venga respinta per riga occupata finché il salvataggio non chiude, e che poi vada a buon fine (nessuno stallo permanente).
  - Verificato che i 15 test esistenti del modulo formazioni (incluso quello con 6 salvataggi paralleli) continuano a passare dopo la modifica.
- **Waiver — verificato, nessun bug.** `resolve_session` (svincoli e asta condividono lo stesso metodo e lo stesso lock su sessione + offerte) era già testato per l'asta ma non per il ramo svincoli, che in più scambia uno slot occupato invece di limitarne uno libero. Aggiunto un test dedicato: 4 risoluzioni concorrenti della stessa sessione svincoli producono uno scambio e un solo addebito, mai duplicati.
- **Approvazione admin di una trade — verificato, nessun bug.** Stesso pattern di lock già testato per accetta/rifiuta del destinatario (`_lock_pending_approval_proposal` come `_lock_actionable_proposal_as_recipient`), ma mai provato sul percorso amministrativo. Aggiunto un test dedicato: 4 decisioni concorrenti (approva/rifiuta) sulla stessa proposta producono una sola transizione valida, le altre tre respinte.
- **Omologazione/ricalcolo punteggi** — già coperta da test di concorrenza diretti esistenti, nessuna azione necessaria.
- **EP12-02 → `IMPLEMENTED_VERIFIED`** in questo registro (era `EVIDENCE_TEMPLATE`).

## 9. Log di verifica — Blocco C

### C1 — Matrice di parità web/mobile sui 17 flussi minimi (26/09/2026)

Censimento diretto del codice (non prova su dispositivo reale) per ciascuno dei 17 flussi del piano. Documento completo: `docs/operations/matrice_parita_web_mobile.md`.

- **11 flussi su 17 sono equivalenti** tra web e mobile: stessi endpoint, stessi permessi, stessa gestione degli stati (loading/empty/error/success/forbidden). Il flusso formazione/lock (11) è il meglio allineato perché la logica di blocco è condivisa dalle due app tramite `@fantappero/contracts`, non solo simile per caso.
- **Trovato un disallineamento di prodotto concreto, non solo tecnico**: `ADR-0006` (07/09/2026) aveva nascosto sul web la tab "Svincolati", la sezione "Svincolo volontario" e lo "Storico mercato" separato nel mercato, rinominando la tab residua da "Mercato" a "Scambi" — decisione mai propagata al mobile, dove tutti e tre erano ancora visibili e attivi.
- **Altri 4 gap trovati, tutti trasversali a più flussi**: sessione mobile non persistente oltre la chiusura dell'app (logout forzato ad ogni riavvio); nessun deep link funzionante sul mobile (link di reset password/invito/join-lega inutilizzabili, solo inserimento manuale); nessuna schermata di completamento verifica email sul mobile (la funzione API esiste, nessuno la chiama); nessun test end-to-end reale sul mobile (nessun Detox/Maestro, solo test banali) — quest'ultimo è esattamente il gap che il criterio C2 del piano chiede di colmare.
- **Non ancora fatto**: la "prova su dispositivo reale" richiesta dal piano per ciascun flusso — il censimento è solo a livello di codice sorgente. **Rimandata di proposito** (decisione dell'utente, 26/09/2026): si completa prima l'analisi da codice su tutti i 17 flussi, la verifica fisica si affronta più avanti insieme al resto del Blocco C.

### C1 (continua) — Completate le colonne mancanti: campi, azioni, messaggi, accessibilità (26/09/2026)

Il primo giro aveva coperto endpoint/permessi/stati/test. Aggiunte le 4 colonne restanti richieste da C1 per tutti i 17 flussi, censimento diretto del codice.

- **Contenuto informativo (campi/azioni/messaggi) sorprendentemente allineato**: per quasi tutti i flussi il testo dei messaggi mostrati all'utente coincide quasi parola per parola tra web e mobile — non solo la logica, anche la formulazione.
- **Trovato un nono problema, trasversale**: accessibilità disomogenea su entrambe le piattaforme, più debole nelle schermate amministrative. Sul web mancano `aria-live` sui messaggi di esito delle azioni admin (uno screen reader non li annuncia automaticamente); sul mobile la maggior parte dei controlli nelle schermate admin ha solo `testID`, senza `accessibilityLabel`/`accessibilityRole` propri — l'unica eccezione è il checkbox di conferma eliminazione lega. Non è un gap di parità (il problema è simile sulle due piattaforme), ma è un difetto reale, non solo teorico.
- **Il flusso matchup H2H (13) è risultato il meglio curato per accessibilità su entrambe le piattaforme**: usa lo stesso helper condiviso per costruire le etichette assistive, quindi il comportamento è identico per costruzione, non per somiglianza casuale — stesso principio già osservato per la logica di lock in formazione (flusso 11).
- **Documento aggiornato**: `docs/operations/matrice_parita_web_mobile.md` ora contiene tutte le 9 colonne richieste da C1 tranne la prova su dispositivo reale (rimandata).

### C1 (continua) — Applicata ADR-0006 anche al mobile (26/09/2026)

Corretto il disallineamento più rilevante trovato sopra, su richiesta esplicita dell'utente.

- **`apps/mobile/src/navigation/marketHubTabs.ts`**: aggiunto `SHOW_WAIVER_TAB = false` (stesso nome/pattern del flag web in `MarketHubPage.tsx`), tab "Svincolati" filtrata dalla lista condivisa `MARKET_HUB_TABS` (usata da tutte e 4 le schermate mercato/rosa/asta/svincoli tramite lo stesso screen-tabs strip); tab residua rinominata da "Mercato" a "Scambi".
- **`apps/mobile/src/screens/MarketScreen.tsx`**: aggiunti `SHOW_VOLUNTARY_RELEASE = false` e `SHOW_MARKET_HISTORY = false` (stessi nomi del flag web in `MarketPage.tsx`), sezioni "Svincolo volontario" e "Storico mercato" nascoste con lo stesso pattern condizionale.
- **Nulla è stato cancellato**: schermata `WaiverScreen`, componenti `MarketReleaseSection`/`MarketHistorySection`, endpoint e stato restano nel codice — stessa filosofia di ADR-0006 ("riportare a `true` il flag per riattivare", nessuna migrazione o modifica backend necessaria).
- **Verificato**: `pnpm run typecheck` pulito, tutti i 31 test mobile esistenti passano invariati (nessun test copriva le sezioni nascoste, quindi nessun test da marcare `.skip` come fatto sul web).
- **Aggiornata la matrice** (`matrice_parita_web_mobile.md`): il flusso 10 (asta/mercato) passa da "Gap" a coerente con il web; restano aperti i 4 gap trasversali elencati sopra, da confermare uno per uno con l'utente prima di intervenire.

### C2 — Prerequisiti risolti prima del test E2E mobile (26/09/2026)

Il flusso E2E richiesto dal piano (registrazione → verifica email → login → lega → rosa → formazione → risultato → mercato → **logout/login con sessione conservata**) non era eseguibile: due dei suoi passaggi erano rotti sul mobile (problemi #2 e #4 di C1). Su decisione esplicita dell'utente, risolti prima di costruire il test.

- **Problema #2 risolto**: `apps/mobile/src/session/sessionStorage.ts` usava una `Map` in memoria — chiusura completa dell'app = logout forzato sempre. Sostituita con `expo-secure-store` (Keychain iOS / Keystore Android), con fallback a `localStorage` solo per `expo start --web` (uso di sviluppo, la web app reale resta `apps/web`). Interfaccia pubblica invariata, nessun altro file da toccare.
- **Problema #4 risolto**: aggiunta `AuthVerifyEmailScreen` (stesso pattern già usato da `AuthResetPasswordScreen`: campo per incollare il codice a mano, dato che i deep link restano non funzionanti — problema #3, non ancora affrontato), raggiungibile dal messaggio di successo della registrazione ("Ho un codice di verifica").
- **Verificato**: `pnpm run typecheck` pulito, tutti i 31 test mobile esistenti passano.
- **Prossimo passo**: costruire ed eseguire il test E2E vero con Maestro su emulatore Android (SDK già presente sulla macchina, nessun AVD ancora configurato). Delegato a un ambiente cloud su richiesta dell'utente, per non occupare risorse locali e sfruttare l'accelerazione hardware Linux (KVM) per l'emulatore.

### C3 — Verifica ambiguità demo/reale (26/09/2026)

Solo verifica sul codice, nessuna modifica. Controllati singolarmente i 4 rischi citati dal criterio di chiusura C3 (che l'utente possa credere di vedere dati reali quando in realtà sta vedendo la demo, o viceversa).

- **`?persona=` sul web è bloccato a livello di build, non solo a runtime**: `isDemoPersonaActive` (`apps/web/src/auth/AuthContext.tsx`) controlla prima `import.meta.env.DEV` e solo se vero legge il parametro `persona` dall'URL. In una build di produzione (`DEV` è `false` per costruzione di Vite) il parametro non ha alcun effetto, qualunque cosa contenga l'URL — non è un flag che si possa dimenticare acceso, è escluso dal bundle di produzione stesso. Confermato anche dal commento nel codice (`apps/web/src/auth/demoSession.ts`): la sessione demo non può mai produrre un'identità di operatore globale, `/admin` resta protetto solo da un vero ruolo `platform_role=operator`.
- **Nessun successo finto senza risposta backend**: stesso gate — la sessione demo (`DEMO_MEMBER`/`DEMO_LEAGUES`) è raggiungibile solo dietro lo stesso controllo `import.meta.env.DEV`, quindi in produzione ogni dato mostrato viene sempre dalla vera risposta dell'API.
- **Deep link con `?leagueId=`: validati lato server, non creduti sulla parola**: `RequirePermissions.tsx` (`apps/web/src/auth/RequirePermissions.tsx`) legge `leagueId` dall'URL ma lo confronta con l'elenco reale delle leghe dell'utente autenticato (`leagues.find(...)`) e verifica i permessi (`hasPermissions`) prima di attivarlo; se la lega richiesta non è tra le sue o mancano i permessi, mostra "Permessi insufficienti" invece di eseguire l'azione. Un link con un `leagueId` non proprio non dà accesso a nulla.
- **Il mobile non ha una modalità demo raggiungibile**: `apps/mobile/src/wireframes/` (`screenMap.ts`, `WireframePlaceholderScreen.tsx`, ecc.) non è importato da nessun navigator o schermata reale — codice morto, verificato per assenza di riferimenti in tutto `apps/mobile/src`. Nota a parte: `apps/mobile/src/session/DemoSessionContext.tsx` nonostante il nome è il vero provider di sessione in produzione (chiama le API reali di autenticazione e leghe) — non va confuso con una modalità demo; il file `demoSession.ts` accanto è solo una funzione helper pura, senza alcun dato finto raggiungibile dall'utente.
- **Esito**: nessun problema trovato, criterio C3 verificato e chiuso.

### C2 (continua) — Test E2E Maestro eseguito con successo, bug reale trovato e corretto (27/09/2026)

Ripreso il lavoro sospeso: eseguito davvero il flusso `apps/mobile/e2e/maestro/flows/full-season-smoke.yaml` su emulatore Android locale (Maestro CLI 2.10.0, Pixel 6/API 33), non solo scritto. **Tutti i 13 passi ora passano**, incluso il punto critico (sessione ancora attiva dopo `stopApp`+`launchApp`, non solo dopo navigazione interna) — prova diretta, non solo teorica, che il fix di C2 sulla persistenza sessione funziona.

- **Ambiente**: oltre a backend/db/posta serve anche il container `worker` (l'invio email passa da una coda Celery). Il worker principale, occupato con sync dati sportivi reali (`--concurrency=1`), può far restare l'email in coda per minuti — usato un secondo worker temporaneo dedicato solo alla posta durante la prova, rimosso a fine sessione.
- **7 correzioni al test** (dettaglio completo in `apps/mobile/e2e/maestro/README.md`): sintassi `timeout`/`extendedWaitUntil`, tastiera che copriva campi in 3 form, dominio email finto rifiutato dal backend, `http.get().body` da parsare esplicitamente con `JSON.parse` (non già oggetto come assunto), destinazione post-creazione lega (Amministrazione lega, non Home lega), link Rosa/Formazione/Turni fuori dallo schermo visibile (serve `scrollUntilVisible`), tab di default sbagliata sulla schermata Turni.
- **1 bug reale trovato e corretto nell'app** (non nel test): `GET /leagues/{id}/turni/da-aggiornare` rispondeva sempre 422 per un problema di **ordine delle rotte** in `backend/src/fantasy_turns/router.py` — la rotta generica `/{league_id}/turni/{round_id}` era dichiarata prima di quella specifica `/{league_id}/turni/da-aggiornare`, quindi FastAPI provava a interpretare "da-aggiornare" come un id e falliva il parsing. **Non tocca la logica del calendario/turni** (solo l'ordine di due dichiarazioni) — riprodotto con una chiamata diretta prima della modifica, confermato risolto dopo, verificata la suite `tests/integration/fantasy_turns/` (22/23 passano, l'unico fallito è preesistente e non collegato). Probabilmente colpiva anche il web, che condivide lo stesso backend.
- **Limite noto, non affrontato**: il passo formazione non prova il salvataggio vero — una lega appena creata ha rosa vuota, non esiste un modo a un tap per popolarla dal mobile. Servirebbe un seed diretto sul DB di test per un test più completo.
- **Blocco C2 chiuso.** Con C1 e C3 già chiusi, l'intero Blocco C del piano di chiusura è completo.

## 10. Log di verifica — Blocco D

### D1 — Manifest della release candidate (27/09/2026)

Creato `docs/operations/release_candidate_fase1.md`: commit esatto, branch, revisione database (`37c365bf2399`, testa unica), stato dei 4 flag di funzionalità (allineati su web/mobile dopo C1), e un elenco onesto di cosa manca per una release "vera" — nessuna versione semantica (tutto fermo a `0.0.0`), nessun tag Git mai creato, nessuna immagine Docker pubblicata su un registry. Nessuno di questi tre punti blocca D2-D4, ma bloccano la distribuzione reale ai tester del pilota (Blocco G) — da affrontare più avanti, non ora. Le prove di performance e sicurezza di agosto (EP12-03/04) segnate esplicitamente come da rifare (D3/D4): oltre un mese di modifiche non riviste, incluso il nuovo storage sicuro della sessione mobile.

### D2 — Gate CI: 5 gap chiusi (27/09/2026)

Confrontato il piano con `.github/workflows/ci.yml` riga per riga. Già a posto: lint/format, test backend/frontend, build pacchetti/web, migrazioni su database vuoto, secret scan, scansione sicurezza statica (bandit). Trovati e chiusi 5 gap:

1. **Type-check Python assente.** Aggiunto mypy — **informativo**, non bloccante: primo giro, 300 errori in 47 file su 306, codice mai controllato prima. Bloccarlo subito avrebbe fermato ogni merge per errori preesistenti, non per regressioni introdotte ora. Config in `backend/pyproject.toml` (`[tool.mypy]`), job `python-typecheck` in CI, target `make typecheck-python`.
2. **"Build mobile" in CI non costruiva nulla di reale**: lo script `build` di `apps/mobile` era testualmente identico a `typecheck` (`tsc --noEmit`) — puro lavoro duplicato, mai verificato che l'app si potesse davvero impacchettare. Sostituito con `expo export --platform ios --platform android`: bundle Metro reale per entrambe le piattaforme, ~15s, nessuna variabile d'ambiente richiesta.
3. **Nessun test di migrazione su database popolato**: solo su database vuoto. Aggiunto `test_last_migration_applies_cleanly_to_a_populated_database` in `backend/tests/integration/database/test_migrations.py` — arriva a un passo dalla testa, popola con dati realistici (stesso seed usato per le prove di carico EP12-03: utenti, leghe, rose validate, formazioni, risultati — non righe sintetiche minime), poi applica l'ultima migrazione sopra. Già dentro il job obbligatorio `migrations` esistente, nessun job nuovo.
4. **E2E critico web non partiva più da solo**: agganciato a un branch `claude/M5` ormai inesistente (interamente incluso nella storia del branch attuale, verificato con `git merge-base --is-ancestor` — nessun lavoro perso, solo un nome di branch rimasto scritto in un file di configurazione). Corretto: ora parte sugli stessi eventi di tutta la pipeline (PR, push a main/dev, avvio manuale). Resta informativo per i merge quotidiani.
5. **E2E critico mobile non esiste in CI.** **Decisione esplicita, su richiesta dell'utente**: resta uno strumento manuale, non collegato a GitHub Actions. Farlo girare in CI richiederebbe avviare un emulatore Android ad ogni esecuzione — 15-25+ minuti di "minuti Actions" (il budget di GitHub per i controlli automatici, un costo separato da quello della sessione con l'assistente), sproporzionato per un controllo da fare solo prima del pilota, non su ogni modifica quotidiana.

**Nota di processo aggiunta al manifest D1**: prima di dichiarare una candidata pronta per il pilota, controllare a mano che l'ultima esecuzione dell'E2E web sia verde ed eseguire l'E2E mobile una volta sullo stesso commit — i due controlli non automatici restano comunque un passaggio obbligato del processo, solo non della pipeline.

**Blocco D2 chiuso.** Nessuna modifica al codice applicativo (solo CI, test, configurazione) — il commit di riferimento nel manifest D1 è stato aggiornato di conseguenza. Prossimo: D3 (performance) e D4 (sicurezza).

### D3 — Performance e capacità rieseguite (27/09/2026)

Rieseguiti tutti gli scenari esistenti (smoke, steady, spike/recovery, 3 benchmark Celery) sul commit attuale, dopo oltre un mese di modifiche non ancora misurate (fix B5, rotte turni, persistenza sessione mobile, ADR-0006 mobile). Aggiunti due scenari nuovi richiesti dal piano e finora mancanti: "live" (pochi utenti che seguono da vicino una partita) e "mobile con polling" (molti client con schermate aperte in background) — `tools/performance/live_polling.js`, stessi endpoint e stessi intervalli di polling reali del client (`useLive*Polling.ts`). Budget ratificati in `docs/operations/performance_capacity.md`.

- **Tutti gli scenari esistenti confermati entro budget** sul commit attuale: smoke, steady (133 req/s, 0% errori), spike a 60 VU (139 req/s, 0% errori, p95=598ms), i 3 benchmark Celery (ping/dominio/poll-live-disabilitato).
- **2 bug trovati e corretti nel nuovo test, non nell'app**, durante la costruzione degli scenari live/mobile_polling — entrambi assunzioni sbagliate sulla forma delle risposte, non problemi del backend:
  1. Il controllo su `GET /leagues/{id}/turni/{round_id}` cercava un campo `roundId` che non esiste nella risposta (`FantasyTurnDetailResponse` usa `id`) — falliva su ogni singola chiamata. Corretto il nome del campo nel test.
  2. Il controllo su `GET /leagues/{id}/calendario/h2h` assumeva sempre una lista `rounds`, ma l'endpoint risponde legittimamente `null` quando il calendario H2H della lega non è ancora confermato — caso reale, non un errore (le leghe seminate per i test di carico non generano/confermano un calendario). Il test ora accetta `null` come risposta valida. **Limite dichiarato in conseguenza**: senza calendario confermato non esiste mai uno `slotId`, quindi questi due scenari non arrivano mai a interrogare l'endpoint "scontro diretto" sotto carico — misurano solo turno/partita/calendario, non lo scontro H2H vero e proprio. Annotato nello script e in `performance_capacity.md`.
  3. Nessuna modifica al codice applicativo in questo punto — solo al test e alla sua documentazione.
- **Esito finale, tutti gli scenari entro i budget ratificati**: `live` (5 VU) — 300 richieste, 0% errori, p95=75ms; `mobile_polling` (50 VU) — 2.460 richieste, 0% errori, p95=507ms, entrambi sotto la soglia p95<1.500ms per endpoint e check>99%.
- **File toccati**: `tools/performance/live_polling.js` (nuovo), `infra/scripts/run_performance_test.sh` (aggiunti i due scenari alla modalità `full`), `docs/operations/performance_capacity.md` (budget dei due nuovi scenari).

**Blocco D3 chiuso.** Prossimo: D4 (rivalidare la sicurezza) — segnalato esplicitamente in D1 per via del nuovo storage sicuro della sessione mobile (`expo-secure-store`), che tocca proprio la superficie "gestione credenziali" tipicamente in scope di una security review.

### D4 — Sicurezza rivalidata, perimetro completo (27/09/2026)

Rieseguiti tutti gli audit di agosto (dipendenze Python/JS, SAST, secret scan) più la riverifica dal vivo di CORS/rate-limit/guardia Range/upload/privacy, più la revisione della superficie mai vista da agosto (pannello operatore turni, asta live, storage sessione mobile) e il test dinamico di bypass autorizzazione (suite IDOR + test dedicati pannello operatore/asta live). Dettaglio completo in `docs/operations/beta_readiness/ep12-04_security_review.md`, sezione "D4".

- **Nessuna regressione** su nulla di quanto già corretto ad agosto.
- **Superficie nuova (pannello operatore turni, asta live, storage sessione mobile) verificata senza problemi**: permessi corretti su ogni endpoint, test dedicati verdi, token mobile sempre su Keychain/Keystore nativo.
- **2 finding nuovi, entrambi con decisione esplicita**:
  1. **Segreto reale (`API_FOOTBALL_KEY`) rimasto nella cronologia Git**, anche se il file attuale è pulito — quando la review di agosto documentò la scoperta, il valore vero finì per errore anche nel testo del documento stesso, poi redatto solo in una revisione successiva (la cronologia conserva entrambe le versioni). **Rischio accettato in via definitiva su decisione esplicita dell'utente (28/09/2026)** — non verrà ruotata.
  2. **CVE Starlette su limiti form-data** (ignorati per corpi url-encoded): tocca solo 2 endpoint autenticati (upload avatar, import CSV rosa). **Rischio accettato per la Beta su decisione esplicita** — esiste un fix a basso rischio (guardia globale sulla dimensione del corpo, stesso pattern già usato per l'header Range) se si vorrà chiuderlo più avanti.
- Le altre 4 nuove CVE Starlette pubblicate da agosto **non si applicano**: verificato nel codice che non usiamo mai i pattern coinvolti (nessun uso di `request.url.path`/`.hostname`, nessuna classe `HTTPEndpoint`, immagine Docker Linux non Windows).

**Blocco D4 chiuso — nessun finding Critico/Alto aperto.** Con D1-D4 completi, l'intero Blocco D del piano di chiusura è chiuso. Prossimo: Blocchi E (ambiente pilot), F (governance/privacy/supporto), G (pilota reale) — non ancora iniziati, guidati principalmente da decisioni reali dell'utente (infrastruttura, dominio, distribuzione ai tester).

## 11. Log di verifica — Blocco E

### E1 — Ambiente pilota su Railway: creato, parzialmente completo (27-28/09/2026)

Su Railway esisteva già un ambiente "dev" con tutti i servizi (api, worker, beat, web, Postgres, Redis) — non un vero ambiente pilota separato come richiede il piano. Creato un nuovo ambiente **"pilota"** (`railway environment new pilota --duplicate dev`), che clona la topologia dei servizi ma non i dati.

- **Database dedicato e vuoto**: verificato che Postgres/Redis del pilota sono istanze nuove (volumi a 0 byte alla creazione), non condivise con dev (che ha invece 96 utenti/76 leghe/20.537 atleti reali). Migrato allo schema più recente.
- **Segreti copiati per sbaglio da dev, corretti**: `JWT_SECRET_KEY` (era il placeholder di sviluppo, ora un segreto nuovo generato apposta) e `WEB_APP_BASE_URL` (puntava al sito di dev, ora corretto).
- **`API_FOOTBALL_KEY` lasciata invariata (stessa di dev)** — decisione esplicita dell'utente, nonostante sia la stessa chiave del finding D4 sul segreto rimasto nella cronologia Git.
- **Email transazionali reali**: Resend collegato. Trovato che Railway blocca il traffico SMTP in uscita (porta 587, verificato confrontando raggiungibilità locale vs da dentro Railway) — aggiunto un trasporto HTTP alternativo in `backend/src/mail/transport.py` (usa l'API di Resend se `RESEND_API_KEY` è impostata, altrimenti SMTP come prima, nessun impatto su Mailpit in dev/test). Verificato end-to-end contro l'ambiente pilota reale: l'invio funziona quando Resend accetta il destinatario (modalità sandbox dell'account, limita i destinatari finché non si verifica un dominio proprio — non un bug).
- **Storage avatar persistente**: volume Railway collegato su `/data/avatars` (stesso percorso già atteso dal codice, nessuna modifica applicativa necessaria).
- **Trigger di deploy automatico rimossi per il pilota** (4 trigger cancellati: api, worker, beat, web) — su richiesta esplicita dell'utente, dopo aver verificato che il pilota aveva ereditato dagli stessi identici trigger di dev (qualunque push su `main` avrebbe fatto ripartire entrambi gli ambienti insieme). Da ora il pilota avanza solo con un deploy manuale esplicito.
- **Bug scoperto e capito durante il lavoro** (non applicativo, di processo): qualunque cambio di configurazione Railway (variabile, volume) rilancia un deploy che ripesca il codice dal branch `main` configurato come sorgente — non l'ultima versione caricata manualmente. Il servizio `api` è arrivato brevemente in stato `FAILED` per questo motivo (il `main` attuale non ha ancora le migrazioni di questa sessione). Recuperato ricaricando il codice; la causa di fondo (branch `main` non allineato al lavoro di chiusura Fase 1) resta aperta, vedi sotto.

**Messi in coda su richiesta esplicita dell'utente** — da riprendere più avanti, non abbandonati:
- **Dominio e TLS**: nessun dominio ancora registrato/collegato; il pilota gira solo sull'URL gratuito `*.up.railway.app`.
- **Distribuzione mobile controllata** (TestFlight/Play Console): l'utente non ha ancora nessuno dei due account sviluppatore.
- **Logging centralizzato e allarmi**: non affrontati.
- **Verifica di un dominio su Resend**: finché non è fatta, le email reali possono arrivare solo all'indirizzo dell'account Resend stesso, non a indirizzi arbitrari (limite della modalità sandbox, non del codice).
- **Branch `main` disallineato**: il piano di chiusura Fase 1 vive interamente su `claude/fase1-chiusura`, mai mergiato — finché resta così, ogni redeploy Railway non esplicitamente manuale rischia di far ripartire i servizi dal codice vecchio. Il merge in main (o un cambio temporaneo della sorgente Git dei servizi) resta una decisione dell'utente, proposta ma non ancora presa.

Blocco E non ancora chiuso: il criterio del piano ("l'ambiente pilot può essere ripristinato, monitorato e supportato senza dipendere dal computer di sviluppo") richiede ancora dominio, logging/allarmi e backup/disaster-recovery testato (E2, non ancora affrontato) prima di poter dichiarare il blocco completo. Prossimo passo lasciato alla decisione dell'utente.

## 12. Log di verifica — Blocco F

### F1 — Primi ruoli assegnati (28/09/2026)

Il pacchetto F1-F3 esisteva già da una sessione precedente (`docs/operations/beta_pilot_gate.md`, `docs/operations/pilot_support_process.md`, EP12-06/EP12-07) con tutti i ruoli segnati "da assegnare". Su decisione esplicita dell'utente, assegnati 5 dei 7 ruoli a **Rosario Trotta — trottarosario@gmail.com** (decision owner, pilot coordinator, security owner, privacy contact, e primario di incident coordinator/platform owner).

- **Backup di incident coordinator e platform owner: chiuso su decisione esplicita dell'utente (28/09/2026)** — nessun sostituto, rischio accettato per un pilota gestito da una sola persona. Annotato esplicitamente in entrambi i documenti (non lasciato come "da assegnare" dimenticato: se Rosario non è raggiungibile durante un incidente, non c'è oggi un secondo referente in grado di intervenire — rischio noto e accettato, non nascosto).
- **League admin pilot**: resta "da selezionare", una persona per ciascuna lega pilota — non assegnabile finché le leghe non sono formate (Blocco G).
- **F2 (testo informativa privacy)**: non affrontato, resta deliberatamente non scritto da un agente — richiede la stesura/approvazione del privacy contact (ora identificato, vedi sopra).
- **F3 (canali, orari, archivio ticket, comando di cutover DR)**: non ancora affrontato.

Aggiornati i due documenti sorgente (`beta_pilot_gate.md` §1, `pilot_support_process.md` tabella "Decisioni obbligatorie").

### F2 e F3 — Chiusi (28/09/2026)

Su richiesta esplicita dell'utente ("chiudiamo F"), preparate proposte concrete per entrambi, minimali e adatte a un pilota piccolo gestito da una sola persona (non un lancio commerciale) — l'utente le ha approvate.

- **F2**: creato `docs/operations/pilot_privacy_notice.md` — testo completo da mostrare ai tester prima dell'iscrizione (dati raccolti, finalità, retention, come esportare/cancellare l'account — basato sui veri endpoint `/profile/me/export` e `/profile/me/delete` già documentati in `docs/api/privacy.md`, nessun dettaglio inventato), più le due decisioni collegate: minorenni esclusi dal primo pilota, archivio richieste = casella email del privacy contact. Il documento resta esplicitamente etichettato come bozza in attesa di lettura/approvazione finale della persona reale (che coincide con chi ha appena dato l'ok in chat), non un'informativa legale professionale.
- **F3**: confermati in `pilot_support_process.md` i valori proposti (canale, orari, archivio ticket) con scelte pragmatiche da singola persona.

**Un solo punto resta genuinamente aperto, non chiudibile con una decisione**: il comando/procedura di cutover per il disaster recovery non è mai stato provato sull'ambiente Railway reale (solo un drill locale su dataset ridotto in una sessione precedente). Non è una scelta da ratificare — è lavoro tecnico non fatto, appartiene al Blocco E2 del piano (mai iniziato in questa sessione). Va completato prima di invitare tester veri (criterio G2), anche se non blocca la chiusura formale del Blocco F in sé.

**Blocco F chiuso** secondo il proprio criterio di completamento del piano ("ruoli, privacy, canali e soglie sono approvati da persone reali e non lasciati come placeholder"): tutti i placeholder sono stati sostituiti da decisioni reali, esplicite, di una persona reale — compresi i rischi accettati (nessun backup) dichiarati apertamente, non nascosti. Resta l'azione tecnica E2 sopra descritta come prerequisito reale prima del Blocco G, non come parte del criterio F stesso.

### E2 — Tentato backup/restore reale su Railway, bloccato a metà (28/09/2026)

Il meccanismo di backup/restore già costruito in una sessione precedente (`postgres-backup`, `dr_restore_drill.sh`) è pensato per lo stack Docker Compose locale — non esiste su Railway. Trovata un'alternativa migliore: Railway offre un vero point-in-time recovery (PITR) nativo per Postgres, più adatto di un pg_dump fatto in casa.

- **Abilitato PITR** sul Postgres del pilota (`railway postgres pitr enable`): confermato `enabled: true`, `bucketWired: true` (l'archiviazione continua è attiva e collegata al suo storage).
- **Bloccato**: creare un backup manuale di prova (`pitr backup create`) e impostare uno schedule (`pitr schedule set`) falliscono entrambi con "non hai accesso a questa risorsa" — verosimilmente un limite del piano Railway attuale (le funzioni di snapshot/schedule spesso richiedono un piano a pagamento). Un controllo separato (`pitr status` campo `live`) richiede anche una chiave SSH locale non presente — generarla è stata esplicitamente rimandata su richiesta dell'utente.
- **Non verificato**: non è stato quindi possibile dimostrare un vero backup+restore riuscito sull'ambiente reale (solo l'archiviazione continua risulta attiva, non un ripristino provato con misura del tempo impiegato, come richiede il piano).

**Messo in coda su richiesta esplicita dell'utente** — da riprendere più avanti: verificare il piano Railway (probabile causa del blocco), eventualmente generare la chiave SSH, e completare un vero drill di ripristino sul pilota prima di invitare tester veri (prerequisito G2).

## 13. Ripasso punti in coda (28/09/2026)

Su richiesta dell'utente, ripresi in ordine i punti rimasti in sospeso da tutta la sessione, uno alla volta.

### Blocco B — OQ-08 (residuo) e OQ-09 spostati in Fase 2

Decisione esplicita dell'utente: entrambi spostati nel backlog Fase 2 in `docs/data/api_football_open_questions.md`. Motivo: l'intenzione è addestrare un modello ML sui dati storici per il futuro "Rating Beta", non scegliere pesi a mano in una formula v2 statica — lavoro di data science fuori scope per la chiusura Fase 1. La formula v1 attuale (bonus/malus) resta invariata e non è toccata da questa decisione.

### Blocco B — OQ-10 (residuo) chiuso

Policy `was_called_up` decisa su conferma esplicita dell'utente: le statistiche reali vincono sulla lista formazione ufficiale (un giocatore con minuti/voto reali conta come convocato anche se assente dalla lineup). Nessuna modifica al codice necessaria (verificato: nessun riferimento esistente al concetto in `backend/src`). Timing pre-kickoff confermato dall'utente (15-30 minuti prima), chiude anche quella parte senza bisogno di monitoraggio dal vivo. Raccolta un'idea nuova non in scope qui (servizio "probabili formazioni", provider diverso) — spostata nel backlog Fase 2.

### Blocco B — OQ-15 (residuo) spostato in Fase 2

Decisione esplicita dell'utente. Non misurabile sui dati statici disponibili (richiede osservare dal vivo un vero cambio di stagione). Rischio pratico basso per il primo pilota (leghe create su stagione già avviata, non a ridosso dell'apertura) — da riverificare solo se il caso limite si presenta davvero.

**Tutti e 4 i punti in coda del Blocco B sono ora chiusi** (2 spostati in Fase 2 come lavoro futuro di ML — OQ-08/OQ-09 —, 1 chiuso con una policy scritta — OQ-10 —, 1 spostato in Fase 2 come rischio a bassa probabilità — OQ-15). Nessuna modifica al codice applicativo in nessuno dei quattro.

### Blocco D — Rotazione `API_FOOTBALL_KEY` chiusa (28/09/2026)

Su decisione esplicita dell'utente ("il primo puoi pure chiuderlo, non mi interessa"), il finding #20 della revisione di sicurezza passa da "rotazione rimandata" a **rischio accettato in via definitiva** — la chiave non verrà ruotata. Aggiornati `ep12-04_security_review.md` (tabella finding, testo del finding #20, riepilogo D4) e questo registro.

### Blocco D — Guardia dimensione richieste applicata, finding #21 corretto (28/09/2026)

Su decisione esplicita dell'utente, applicato il fix a basso rischio già proposto in D4: `BodySizeGuardMiddleware` (`backend/src/app/security_middleware.py`, registrato in `backend/src/app/main.py`) rifiuta con `413` qualunque richiesta HTTP il cui corpo superi 10 MiB, sia sul `Content-Length` dichiarato (rifiuto immediato) sia mentre il corpo arriva in streaming (copre anche un corpo senza `Content-Length`, es. chunked) — prima che raggiunga il parsing di `request.form()` (l'endpoint dell'avatar e quello di import CSV rosa, gli unici due che lo usano). Stesso schema della mitigazione già in produzione sull'header `Range`.

- **3 test nuovi** in `backend/tests/unit/app/test_security_middleware.py` (corpo piccolo passa; `Content-Length` dichiarato oltre soglia rifiutato prima di leggere il corpo; corpo in streaming oltre soglia rifiutato). Verificato anche dal vivo con `curl`.
- **Nessuna regressione**: `tests/integration/auth/test_profile.py` (include l'upload avatar reale, sotto soglia) verde; `ruff check`/`ruff format --check` puliti su tutti i file toccati.

**Blocco D interamente chiuso** — nessun punto in coda residuo (con D1-D4 già chiusi in precedenza, e ora anche i 2 finding rimasti aperti da D4).

### Blocco E — Dominio e TLS chiusi con il dominio gratuito Railway (28/09/2026)

Su decisione esplicita dell'utente, niente dominio proprio acquistato — usato il dominio gratuito di Railway, con nome coerente con quello di dev (`fantappero-web-dev.up.railway.app` → `fantappero-web-pilot.up.railway.app`). TLS gestito automaticamente da Railway, nessuna configurazione manuale necessaria.

- Rinominato il dominio auto-generato del servizio `web` in pilota (`railway domain update`), aggiornato `WEB_APP_BASE_URL` sul servizio `api` di conseguenza.
- **Bug reale trovato e corretto**: `apps/web/vite.config.ts` aveva `allowedHosts` con solo il dominio di dev in lista fissa — qualunque altro dominio (incluso quello del pilota) veniva respinto dal server Vite con `403 Blocked request`, mai notato prima perché nessuna verifica precedente aveva aperto il sito nel browser (solo chiamate dirette alle API). Aggiunto il dominio del pilota alla lista; verificato dal vivo con `curl -i`, ora risponde `200 OK`.
- **Effetto collaterale incontrato di nuovo**: sia il cambio del dominio sia il cambio di `WEB_APP_BASE_URL` hanno fatto ripartire `api` dal branch `main` (stesso bug già noto — rimuovere i trigger automatici non impedisce che un redeploy per cambio variabile ripeschi comunque dalla sorgente Git configurata). Recuperato ricaricando manualmente il codice del branch; la causa di fondo resta il branch `main` non allineato, non ancora risolta.

**Punto chiuso.** Restano 4 punti in coda nel Blocco E: distribuzione mobile controllata, logging/allarmi, verifica dominio su Resend, backup/restore reale (bloccato dal piano Railway).

### Blocco E — Distribuzione mobile: Android per Fase 1, iOS rimandato a Fase 2 (28/09/2026)

Decisione esplicita dell'utente. Spiegato che, per un pilota piccolo, Android non richiede necessariamente i 25$ di Google Play Console: un file `.apk` costruito via EAS Build può essere condiviso direttamente con i tester (side-load, nessun account richiesto), mentre iOS non ha una scorciatoia gratuita reale — serve comunque l'account Apple Developer (99$/anno) o TestFlight.

- **Android**: resta in coda — l'utente chiederà un `.apk` quando servirà davvero (non prima). Nessuna azione da fare ora.
- **iOS**: spostato esplicitamente nel backlog Fase 2 — nessun account Apple Developer aperto, il primo pilota (Blocco G) partirà solo con tester Android (o via browser web, sempre disponibile a tutti).

### Blocco E — Logging centralizzato e allarmi spostati in Fase 2 (28/09/2026)

Decisione esplicita dell'utente: per ora si resta solo sugli strumenti già inclusi in Railway (`railway logs`, stato dei servizi) — nessuna integrazione aggiuntiva (Grafana Cloud, UptimeRobot) per il primo pilota. Nessun allarme automatico attivo: eventuali problemi vanno controllati a mano finché questo punto non verrà ripreso.

### Blocco E — 3 bug reali trovati e corretti durante la prima prova vera del pilota (28/09/2026)

L'utente ha provato di persona il flusso di registrazione sul pilota (prima volta con dati reali, non un test automatico). Trovati e corretti sul momento:

1. **`VITE_API_BASE_URL` del servizio `web` puntava all'API di dev**, non a quella del pilota — copiato per sbaglio dalla clonazione dell'ambiente, mai notato prima (nessuna verifica precedente aveva aperto il sito vero nel browser). La prima registrazione dell'utente è finita nel database di dev invece che in quello del pilota, spiegando perché "l'email non arrivava" — in realtà l'account veniva creato nell'ambiente sbagliato. Corretto puntando `web` all'API del pilota.
2. **Verifica email: la pagina mandava la richiesta di conferma due volte** (dovuto al doppio invocamento degli effect di React in modalità sviluppo — `StrictMode`), consumando il codice monouso alla prima chiamata (riuscita, `200`) e mostrando poi l'esito della seconda chiamata duplicata (fallita, `400`, codice già usato) — l'utente vedeva "Verifica non riuscita" nonostante l'account fosse già verificato per davvero. Corretto in `apps/web/src/pages/auth/AuthPages.tsx`: la richiesta ora parte una sola volta per sessione della pagina, indipendentemente da quante volte l'effetto viene rieseguito. Aggiunto test dedicato (`AuthVerifyEmailPage.test.tsx`) che riproduce esplicitamente il doppio invocamento di StrictMode.
3. **Su schermo stretto (mobile web), un utente senza leghe non aveva alcun modo di crearne una o unirsi** — i link "Crea lega"/"Unisciti con codice" nell'intestazione erano nascosti del tutto sotto i 767px di larghezza (`display: none` in `packages/ui/src/css/layout.css`), probabilmente pensati per essere spostati altrove (es. il menu ad hamburger) ma quello spostamento non è mai stato fatto — lasciando un vicolo cieco reale per qualunque nuovo utente su mobile. Corretto: i link restano visibili e vanno a capo se necessario, invece di sparire.

Tutti e 3 i fix distribuiti manualmente sul pilota e verificati dal vivo dall'utente durante la sessione stessa. Nessun test automatico esisteva per nessuno dei tre casi prima di oggi — il primo trovato dalla verifica manuale del sito vero, non da un test scritto in anticipo.

### Blocco E — Tentativo di verifica dominio su Resend con `globetrotta.it`, abbandonato (28/09/2026)

L'utente possiede un dominio personale (`globetrotta.it`, gestito su Aruba, non dedicato a FantApperò) e ha proposto di usarlo solo per le email del pilota. Registrato un sottodominio dedicato (`fantappero.globetrotta.it`) su Resend per non toccare la posta esistente del dominio principale.

- **DKIM (TXT) e SPF (TXT) verificati con successo** — record aggiunti su Aruba, confermati propagati con un controllo DNS diretto (non solo tramite Resend).
- **Bloccato sul record MX**: il pannello "Gestione DNS" di Aruba per domini con posta attiva (`Dominio con email`) **non offre MX tra i tipi di record disponibili** nell'interfaccia base — probabilmente una scelta deliberata di Aruba per evitare che un cliente rompa la propria posta esistente per errore. Confermato con una query DNS diretta: il record MX richiesto da Resend semplicemente non esiste.
- **Verificato che cambiare dominio (usare `globetrotta.it` direttamente invece del sottodominio) non avrebbe risolto nulla**: Resend richiede comunque l'MX su un proprio sottodominio dedicato (`send.*`) indipendentemente dal dominio scelto — il limite è del pannello Aruba, non della scelta del sottodominio.
- **Decisione dell'utente**: abbandonare questo tentativo, non contattare l'assistenza Aruba per ora — passerà a un dominio dedicato (provider ancora da scegliere) quando pronto. Ripulito il lato Resend (dominio parziale cancellato); l'utente ha ripulito i record aggiunti su Aruba.

**Il punto "verifica dominio su Resend" spostato esplicitamente nel backlog Fase 2** su decisione dell'utente (28/09/2026) — valutata anche l'opzione di spostare il DNS di `globetrotta.it` su Cloudflare (gratuito, risolverebbe il limite MX di Aruba senza comprare un dominio nuovo), scartata per ora. La procedura da rifare quando si sceglierà un dominio dedicato è la stessa già documentata sopra (pochi minuti, non da reinventare).

**Con questo si chiude anche l'ultimo punto in coda "attivo" del Blocco E** — resta solo il backup/restore reale (E2, bloccato dal piano Railway + chiave SSH, vedi sezione 11) prima del Blocco G.

### Blocco E2 — Backup/restore reale spostato nel backlog Fase 2 (28/09/2026)

Ripresa l'indagine sul blocco di `pitr backup create`/`schedule set`: l'errore preciso restituito da Railway è `OAUTH_INSUFFICIENT_GRANT` (permesso mancante sulla sessione collegata alla CLI, non necessariamente un limite di piano). Tentato un nuovo login per ottenere un permesso più ampio — 4 tentativi falliti (3 scaduti per timeout del callback browser, non raggiungibile da questo ambiente; 1 codice dispositivo scaduto perché l'utente non era al computer).

**Decisione esplicita dell'utente**: il backup reale richiede comunque un cambio di piano Railway a pagamento — spostato l'intero punto nel backlog Fase 2, non insistere oltre con il login. Nota tecnica lasciata per quando si riprenderà: l'errore preciso è `OAUTH_INSUFFICIENT_GRANT`, non un rifiuto esplicito di piano — da verificare comunque, al momento di riprendere, se serva solo un nuovo login con permessi più ampi o se sia davvero necessario un piano superiore, prima di procedere all'eventuale upgrade.

**Blocco E ora interamente chiuso o spostato in Fase 2** — nessun punto attivo residuo prima del Blocco G, a parte l'esecuzione del pilota vero stesso.

### Blocco F2 — Testo privacy approvato (28/09/2026)

Il privacy contact (Rosario Trotta) ha letto e approvato esplicitamente il testo proposto in `docs/operations/pilot_privacy_notice.md`, senza richiedere modifiche. Aggiornato lo stato del documento da "bozza in attesa" ad "approvato". **Blocco F ora chiuso al 100%, nessun loose end residuo.**

**Con questo, tutti i blocchi A-F del piano di chiusura Fase 1 sono chiusi (o esplicitamente spostati in Fase 2 dove pertinente). Resta solo il Blocco G — il pilota reale — mai iniziato, l'unico pezzo davvero mancante per dichiarare la Fase 1 completa.**