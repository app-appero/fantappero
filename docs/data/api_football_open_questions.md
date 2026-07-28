# Registro open questions API-Football — input EP00-02

| Metadato | Valore |
| --- | --- |
| Origine | EP00-01 |
| Consumatore | EP00-02 (collaudo payload reali) |
| Versione | 0.1.0 |
| Vincolo | Nessuna chiave API, nessun payload grezzo con dati sensibili in repo. Nei test EP00-02 salvare solo fixture anonimizzate/congelate o path di campo + hash. |
| Corpus offline | `backend/tests/fixtures/api_football/` — vedi [`dataset_coverage.md`](./dataset_coverage.md) (**v0.2.0**, provenance `provider_v3`). Validare con `python backend/scripts/validate_sports_dataset.py`. |

Questo registro elenca **solo** ciò che la documentazione pubblica e i requisiti di prodotto non chiudono. Ogni voce va verificata su JSON reali dei cinque campionati.

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

### OQ-08 — Coverage e completezza stats sui 5 campionati

| Campo | Valore |
| --- | --- |
| Priorità | P0 |
| Endpoint | `/leagues` coverage + `/fixtures/players` |
| Domanda | Per stagione attiva, `statistics_players` / `events` / `lineups` / `injuries` sono `true`? Quali campi stats risultano frequentemente `null`? |
| Impatto | Rating Beta e bonus |
| Evidenza richiesta EP00-02 | Tabella coverage per league 39/140/135/78/61; % null per campo candidato Rating |
| Criterio chiusura | Lista campi ammessi in formula v1 vs esclusi per qualità |

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

### OQ-11 — Infortuni vs squalifiche e overlapping `/sidelined`

| Campo | Valore |
| --- | --- |
| Priorità | P1 |
| Endpoint | `/injuries` (`type`, `reason`); eventuale `/sidelined` (fuori scope EP00-01 ma correlato) |
| Domanda | `type` distingue sempre Injury/Suspension? `reason` è stabile o free-text? Serve `/sidelined` nell’MVP? |
| Impatto | Esclusione 6 d’ufficio; IA |
| Evidenza richiesta EP00-02 | Campione injuries per league; decisione su `/sidelined` |
| Criterio chiusura | Enum interno; niente parsing NLP di `reason` |

### OQ-12 — Transfer Loan / temporanei / uscita dai 5 campionati

| Campo | Valore |
| --- | --- |
| Priorità | P1 |
| Endpoint | `/transfers`, `/players/squads` |
| Domanda | Come rilevare in modo affidabile “uscita dai cinque campionati” per credito 100%? Come trattare Loan e date mancanti? `/players/squads` senza `season` basta per membership corrente? |
| Impatto | FR-MKT-02, FR-ROS-01 |
| Evidenza richiesta EP00-02 | Casi trasferimento inter-lega big-5, fuori big-5, loan |
| Criterio chiusura | Regole auto vs coda admin (allineate a FR-MKT-02) |

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
