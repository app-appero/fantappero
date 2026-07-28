# Matrice requisiti ↔ API-Football v3

| Metadato | Valore |
| --- | --- |
| Codice card | EP00-01 |
| Versione | 0.1.0 |
| Stato | Draft — validazione payload reali in EP00-02 |
| Provider | API-Football v3 (`https://v3.football.api-sports.io`) |
| Riferimenti prodotto | Documento Master v0.1 §15; Requisiti funzionali MVP v0.1 (FR-DAT/FR-SCO/FR-TUR/FR-ROS/FR-AI/FR-RIN); Architettura tecnica MVP v0.1 §4 |
| Documentazione provider | https://api-sports.io/documentation/football/v3 e https://www.api-football.com/documentation-v3 |
| Regola di redazione | Nessuna assunzione di dominio inventata: dove il mapping non è chiuso nei documenti di prodotto, compare **Gap** o **Da verificare (EP00-02)**. Nessuna chiave API né payload sensibile in questo file. |

## 1. Come leggere la matrice

### Classificazione campi

| Classe | Significato |
| --- | --- |
| **Obbligatorio** | Necessario per un requisito critico (listone, turni, formazione/lock, bonus/malus, Rating Beta, o input IA obbligatorio al funzionamento). Senza fonte o con fonte ambigua → gap bloccante. |
| **Derivato** | Non arriva come fatto unico dal provider; si ottiene da regole interne su uno o più campi esterni. |
| **Opzionale** | Utile a UX, IA o qualità, ma non richiesto per chiudere il calcolo deterministico MVP. |
| **Non affidabile** | Presente nel provider ma non utilizzabile come verità di scoring senza collaudo o decisione di prodotto. |

### Criticità

| Livello | Significato |
| --- | --- |
| **Bloccante** | Impedisce listone, turni, lock, fantavoto o omologazione se assente/ambiguo. |
| **Alto** | Compromette qualità (sostituzioni, rinvii, mercato, spiegabilità) ma esiste fallback esplicito. |
| **Medio** | Supporto IA / contesto / UX. |
| **Basso** | Nice-to-have. |

### Persistenza interna (modello Architettura §7.2)

Entità normalizzate previste: `competition`, `sport_season`, `club`, `athlete`, `squad_membership`, `role_assignment`, `fixture`, `match_event`, `player_match_stat`, `provider_snapshot`, più snapshot di supporto (`official_lineup`, `availability`, `transfer`, `provider_prediction_snapshot`).

I domini fantasy leggono **solo** queste entità, non i path/campi grezzi del provider (ADR-0001).

### Competizioni MVP (ID v3 pubblicati)

Da confermare in EP00-02 contro `/leagues` e flag `coverage` per la stagione attiva:

| Campionato | `league.id` documentato |
| --- | --- |
| Premier League | 39 |
| La Liga | 140 |
| Serie A | 135 |
| Bundesliga | 78 |
| Ligue 1 | 61 |

`season` = anno di inizio stagione (es. 2025/26 → `2025`).

---

## 2. Copertura endpoint previsti

Ogni endpoint nello scope EP00-01 compare almeno una volta.

| Endpoint | Entità interne | Uso FantApperò | FR principali |
| --- | --- | --- | --- |
| `/leagues` | `competition`, `sport_season` | Anagrafica 5 campionati; gate `coverage.*` | FR-DAT-01, FR-ROS-01, FR-TUR-01 |
| `/teams` | `club` (+ venue accessorio) | Club del listone / membership | FR-DAT-01, FR-ROS-01 |
| `/players` | `athlete` (+ stats stagione) | Profilo calciatore, ruolo grezzo, foto, flag injured | FR-DAT-01, FR-ROS-01, FR-AI-02 |
| `/players/squads` | `squad_membership` | Rosa ufficiale club (listone) | FR-DAT-01, FR-ROS-01 |
| `/fixtures` | `fixture`, `fixture_status` | Turni, kickoff lock, rinvii, risultati | FR-TUR-01, FR-TUR-02, FR-RIN-*, FR-OMO-01 |
| `/fixtures/events` | `match_event` | Bonus/malus e timeline | FR-SCO-02, FR-DAT-01 |
| `/fixtures/lineups` | `official_lineup` | Convocati / titolarità ufficiale (rinvio d’ufficio, IA) | FR-RIN-01, FR-AI-01 |
| `/fixtures/players` | `player_match_stat` | Minuti, stats Rating Beta, benchmark rating provider, parte bonus | FR-SCO-01, FR-SCO-02, FR-SUB-01 |
| `/injuries` | `availability` | Infortuni/squalifiche | FR-RIN-01, FR-AI-*, FR-MKT-02 (contesto) |
| `/transfers` | `transfer` | Uscite dai 5 campionati, riconciliazione listone | FR-ROS-01, FR-MKT-02 |
| `/standings` | (snapshot classifica reale) | Contesto IA / Analista | FR-AI-02 |
| `/predictions` | `provider_prediction_snapshot` | Solo segnale IA, mai verità di scoring | FR-AI-01, FR-AI-02 |

---

## 3. Matrice per endpoint

Legenda colonne: **Campo esterno** (path JSON documentato o descritto dalla guida ufficiale API-Football), **Semantica**, **Disponibilità temporale**, **Trasformazione interna**, **FR**, **Classe**, **Criticità**, **Fallback**, **Persistenza**.

### 3.1 `/leagues`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `league.id` | ID stabile competizione v3 | Sempre (catalogo) | `competition.provider_id` | FR-DAT-01, FR-ROS-01 | Obbligatorio | Bloccante | Nessuno: senza ID non si sincronizza | `competition` |
| `league.name` / `league.country` / `league.logo` | Anagrafica display | Sempre | Copia normalizzata | FR-DAT-01 | Opzionale | Medio | Nome interno configurato | `competition` |
| `seasons[].year` | Stagione provider | Catalogo + `current` | `sport_season.year` | FR-DAT-01, FR-TUR-01 | Obbligatorio | Bloccante | Config stagione piattaforma | `sport_season` |
| `seasons[].start` / `end` | Finestra stagione | Catalogo | Bound calendarizzazione | FR-TUR-01 | Opzionale | Alto | Finestre configurate admin | `sport_season` |
| `seasons[].coverage.fixtures.events` | Provider dichiara eventi | Per stagione | Gate job eventi | FR-DAT-01, FR-SCO-02 | Obbligatorio | Bloccante | Se `false` → gap bloccante per quel campionato/stagione | `provider_snapshot` + flag stagione |
| `seasons[].coverage.fixtures.lineups` | Dichiarazione lineup | Per stagione | Gate job lineup | FR-RIN-01, FR-AI-01 | Obbligatorio | Alto | Se assente: rinvio d’ufficio in eccezione admin (FR-RIN-01) | flag stagione |
| `seasons[].coverage.fixtures.statistics_players` | Dichiarazione stats giocatore | Per stagione | Gate job stats | FR-SCO-01, FR-SCO-02 | Obbligatorio | Bloccante | Nessuno per scoring | flag stagione |
| `seasons[].coverage.injuries` | Dichiarazione injuries | Per stagione | Gate job availability | FR-RIN-01, FR-AI-* | Opzionale | Alto | Eccezione admin se convocazione assente | flag stagione |
| `seasons[].coverage.predictions` | Dichiarazione predictions | Per stagione | Gate IA | FR-AI-* | Opzionale | Medio | IA senza predizione provider | flag stagione |
| `seasons[].coverage.standings` | Dichiarazione standings | Per stagione | Gate IA | FR-AI-02 | Opzionale | Basso | Nessuno | flag stagione |

### 3.2 `/teams`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `team.id` | ID club stabile cross-competizione | Sempre | `club.provider_id` | FR-DAT-01, FR-ROS-01 | Obbligatorio | Bloccante | Nessuno | `club` |
| `team.name` / `team.code` / `team.logo` / `team.country` | Anagrafica | Sempre | Copia | FR-ROS-01 | Obbligatorio (name) / Opzionale (resto) | Alto | Solo name minimo | `club` |
| `team.national` | Club vs nazionale | Sempre | Filtro: MVP usa solo club di campionato | FR-ROS-01 | Derivato (filtro) | Medio | Esclusione se `true` fuori perimetro | `club` |
| `venue.*` | Stadio | Spesso | Opzionale, non usato dallo scoring | — | Opzionale | Basso | Ignora | opzionale / non MVP scoring |

### 3.3 `/players`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `player.id` | ID calciatore provider | Sempre | `athlete.provider_id` | FR-ROS-01, FR-DAT-01 | Obbligatorio | Bloccante | Nessuno | `athlete` |
| `player.name` / `firstname` / `lastname` | Nome | Sempre | `canonical_name` (+ display) | FR-ROS-01 | Obbligatorio | Bloccante | Nessuno | `athlete` |
| `player.photo` | URL media (CDN non quota) | Spesso | Cache asset | UX | Opzionale | Basso | Placeholder | asset cache |
| `player.nationality` / `birth.*` / `height` / `weight` / `age` | Profilo | Variabile | Anagrafica | FR-AI-02 | Opzionale | Basso | Null consentito | `athlete` |
| `player.injured` | Flag booleano disponibilità grezza | Aggiornato “as information comes in” (doc provider) | Segnale leggero; **non** sostituisce `/injuries` | FR-AI-*, FR-RIN-01 | Non affidabile (da solo) | Alto | Preferire `/injuries`; se assente → non presumere idoneità (FR-RIN-01) | flag su `athlete` o availability |
| `statistics[].league.id` + `statistics[].team.id` | Contesto stagione/competizione/club | Con `season` | Membership e filtro 5 campionati | FR-ROS-01 | Obbligatorio | Bloccante | Cross-check `/players/squads` | `squad_membership` |
| `statistics[].games.position` | Ruolo grezzo provider (es. Goalkeeper / Defender / Midfielder / Attacker) | Per stagione/competizione | Input a `role_assignment` P–D–C–A (**mapping prodotto**, non assunto qui) | FR-ROS-01, FR-LEG-02 | Obbligatorio come input; mapping = Derivato | Bloccante | Ruolo listone FantApperò / override admin | `role_assignment` |
| `statistics[].games.appearences` / `minutes` / totals stagione | Aggregati stagione | Post-inizio stagione | Solo contesto IA / listone, **non** fantavoto partita | FR-AI-02 | Opzionale | Medio | Ignora | stats stagione opz. |
| Paginazione `paging.*` | 20/page | Sempre | Job deve paginare fino a `paging.total` | FR-DAT-01 | Obbligatorio (operativo) | Alto | Job incompleto = listone incompleto | job metadata |

### 3.4 `/players/squads`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `team.id` | Club della rosa | Parametro `team` | Chiave membership | FR-ROS-01 | Obbligatorio | Bloccante | Nessuno | `squad_membership` |
| `players[].id` | Calciatore in rosa corrente | “Current squad” (doc: **niente parametro season**) | Upsert membership attiva | FR-ROS-01 | Obbligatorio | Bloccante | Integrare con `/players?team&season` | `squad_membership` |
| `players[].name` / `age` / `number` / `position` / `photo` | Anagrafica rosa | Sempre nella risposta squad | Supporto listone; `position` → stesso problema mapping ruolo | FR-ROS-01 | Obbligatorio (id+name+position) | Alto | Override admin | `athlete` / `role_assignment` |

**Nota di dominio (non assunzione operativa):** la doc provider non garantisce storico stagionale su `/players/squads`. La reconciliation temporale listone ↔ transfer resta gap di processo (vedi open questions).

### 3.5 `/fixtures`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fixture.id` | ID partita | Sempre | `fixture.provider_id` | FR-TUR-01, FR-DAT-01 | Obbligatorio | Bloccante | Nessuno | `fixture` |
| `fixture.date` / `fixture.timestamp` | Kickoff (ISO / Unix UTC) | Pre-partita; aggiornabile | Kickoff lock; timezone server autoritativo | FR-TUR-02 | Obbligatorio | Bloccante | Se manca → non pubblicare nel turno | `fixture.kickoff` |
| `fixture.status.short` | Codice stato (`NS`,`1H`,`HT`,`2H`,`FT`,`PST`,`CANC`,`SUSP`, …) | Live ~15s; storico stabile | Macchina a stati interna | FR-TUR-02, FR-RIN-*, FR-OMO-01 | Obbligatorio | Bloccante | Ultimo stato noto + timestamp; non inventare FT | `fixture_status` |
| `fixture.status.elapsed` / `long` | Minuto / label | Live | UX live | — | Opzionale | Medio | Nascondi | status snapshot |
| `league.id` / `league.season` / `league.round` | Contesto competizione | Sempre | Filtro 5 campionati; round **non** è il turno FantApperò | FR-TUR-01 | Obbligatorio (league/season); round Opzionale | Bloccante / Basso | Turno Fantasy da finestra temporale interna | `fixture` |
| `teams.home.id` / `teams.away.id` | Club | Sempre | Home/away | FR-TUR-01 | Obbligatorio | Bloccante | Nessuno | `fixture` |
| `goals.home` / `goals.away` + `score.*` | Punteggio | Live/FT | Contesto; clean sheet portiere = Derivato da gol subiti squadra / stats | FR-SCO-02 | Derivato (CS) / Opzionale (display) | Alto (CS) | Preferire `goals.conceded` portiere + eventi | score su fixture |
| `fixture.referee` / `venue.*` | Metadati | Variabile | Non scoring | — | Opzionale | Basso | Ignora | opzionale |

**Regola prodotto già chiusa:** ogni fixture appartiene a **un solo** turno FantApperò (FR-TUR-01). Il turno non replica `league.round`.

### 3.6 `/fixtures/events`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Chiave logica evento | Identità anti-duplicazione | Live ~15s; correzioni post-FT | `provider_event_key` (composizione da verificare in EP00-02: ordine+minuto+type+player+detail…) | FR-DAT-01, FR-SCO-02 | Obbligatorio (derivato) | Bloccante | Hash payload + ordine stabile; mai doppio bonus | `match_event` |
| `time.elapsed` / `time.extra` | Minuto | Per evento | Timeline + recovery | FR-SCO-02 | Obbligatorio | Alto | `elapsed` solo | `match_event` |
| `team.id` | Squadra evento | Per evento | Contestualizza | FR-SCO-02 | Obbligatorio | Alto | Nessuno per eventi rilevanti | `match_event` |
| `player.id` | Autore primario | Per evento (può essere null in casi limite) | Athlete link | FR-SCO-02 | Obbligatorio | Bloccante | Se null → dead-letter / review | `match_event` |
| `assist.id` | Assistente su Goal | Su gol con assist | Bonus assist +1 | FR-SCO-02 | Obbligatorio quando presente | Bloccante (qualità assist) | Cross-check `goals.assists` in `/fixtures/players` | `match_event` |
| `type` | `Goal` / `Card` / `subst` / `Var` (doc) | Per evento | Router regole | FR-SCO-02 | Obbligatorio | Bloccante | Eventi sconosciuti → ignore + metric | `match_event` |
| `detail` = `Normal Goal` | Gol | Live/FT | Bonus gol +3 | FR-SCO-02 | Obbligatorio | Bloccante | Nessuno | `match_event` |
| `detail` = `Own Goal` | Autogol | Live/FT | Malus −2; **non** come gol normale | FR-SCO-02, FR-DAT-01 | Obbligatorio | Bloccante | Gap se classificazione assente/ambigua | `match_event` |
| `detail` = `Penalty` | Gol su rigore | Live/FT | Trattato come gol (+3) salvo regola distinta (non presente nei doc prodotto) | FR-SCO-02 | Obbligatorio | Alto | Come Normal Goal se non diversamente deciso | `match_event` |
| `detail` = `Missed Penalty` | Rigore sbagliato | Live/FT | Malus −3 al tiratore | FR-SCO-02 | Obbligatorio | Bloccante | Cross-check `penalty.missed` stats | `match_event` |
| `detail` = `Yellow Card` | Ammonizione | Live/FT | −0,5 | FR-SCO-02 | Obbligatorio | Bloccante | Stats cards | `match_event` |
| `detail` = `Red Card` / `Yellow-Red Card` | Espulsione / doppia ammonizione | Live/FT | −1; **regola cumulativa da regolamento esecutivo** (aperta) | FR-SCO-02 | Obbligatorio | Bloccante | Non sommare in modo ambiguo finché regola non chiusa | `match_event` |
| `detail` sostituzione | Cambio (`subst`) | Live | Non è bonus; può aiutare minuti/titolarità | FR-SUB-01, FR-AI-01 | Opzionale | Medio | Lineup + minutes | `match_event` |
| Eventi `Var` | Annullamenti / conferme | Variabile | Possibile correzione gol | FR-OMO-01 | Non affidabile senza collaudo | Alto | Attendi coerenza events↔stats post-FT | `match_event` |
| Rigore **parato** | Bonus portiere +3 | — | **Non** risulta un `detail` eventi dedicato nella guida ufficiale citata; candidato primario: `penalty.saved` in `/fixtures/players` | FR-SCO-02 | Gap / da verificare | Bloccante | Vedi OQ-EP00-02-07 | — |

### 3.7 `/fixtures/lineups`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `team.id` | Squadra | Tipicamente 20–75 min pre-kickoff (variabile; a volte solo post-gara) | Snapshot ufficiale | FR-RIN-01, FR-AI-01 | Obbligatorio quando usato | Alto | Se assente pre-kickoff: non presumere convocazione | `official_lineup` |
| `formation` | Modulo ufficiale stringa | Con lineup | Solo contesto IA; **non** vincola i 7 moduli fantasy | FR-AI-01 | Opzionale | Medio | Null | `official_lineup` |
| `startXI[].player.id` | Titolari ufficiali | Con lineup | Convocato/titolare per 6 d’ufficio e probabilità titolarità | FR-RIN-01, FR-AI-01 | Obbligatorio per voto d’ufficio | Bloccante (solo path rinvio a tempo) | Eccezione admin (FR-RIN-01) | `official_lineup` |
| `startXI[].player.pos` / `grid` | Ruolo/griglia | Variabile (`grid` non ovunque) | Contesto | FR-AI-01 | Opzionale / Non affidabile (`grid`) | Basso | Ignora | snapshot |
| `substitutes[].player.id` | Panchina ufficiale | Con lineup | Convocati non titolari | FR-RIN-01, FR-AI-01 | Obbligatorio per “convocato” | Alto | Se solo startXI → policy da chiudere | `official_lineup` |
| `coach.*` | Allenatore | Spesso | Non MVP scoring | — | Opzionale | Basso | Ignora | opzionale |

**Confini:** la formazione fantasy (FR-FOR-*) è scelta utente; le lineup ufficiali non la sostituiscono.

### 3.8 `/fixtures/players`

Fonte primaria per **minuti**, **Rating Beta (input statistici)** e parte dei controlli bonus. Aggiornamento dichiarato: ~1 min in live; correzioni post-FT.

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `player.id` | Calciatore | Per chi ha stats | Link athlete | FR-SCO-* | Obbligatorio | Bloccante | Nessuno | `player_match_stat` |
| `games.minutes` | Minuti giocati | Live/FT | Soglia voto (std 15, conf 1–30) | FR-SCO-01, FR-SUB-01 | Obbligatorio | Bloccante | Senza minuti → senza voto salvo eventi rilevanti | `player_match_stat.minutes` |
| `games.substitute` | Entrato dalla panchina | Live/FT | Contesto sub / IA | FR-SUB-01, FR-AI-01 | Opzionale | Medio | Inferire da events subst | stats_json |
| `games.position` | Ruolo in partita | Spesso | Normalizzazione Rating per ruolo (formule versionate) | FR-SCO-01 | Obbligatorio per pesi P/D/C/A | Alto | Ruolo listone | stats_json |
| `games.rating` | Rating 0–10 provider | Spesso a FT | **Benchmark only** (Master §8.3); non voto FantApperò | FR-SCO-01 | Non affidabile come voto | Medio | Conservare, non usare in formula | `provider_rating` |
| `goals.total` | Gol segnati (stats) | Live/FT | Controllo vs events; **non** entra nel voto statistico | FR-SCO-01/02 | Derivato/controllo | Alto | Events primari per bonus | stats_json |
| `goals.assists` | Assist (stats) | Live/FT | Cross-check vs `assist` events | FR-SCO-02, FR-DAT-01 | Obbligatorio (qualità) | Bloccante | Se diverge → stato provvisorio / regola riconciliazione (OQ) | stats_json |
| `goals.conceded` | Gol subiti | Tipico portieri | Malus portiere −1 ciascuno; CS = Derivato (==0 e minuti/titolarità da policy) | FR-SCO-02 | Obbligatorio (P) | Bloccante | Events Goal avversari + ruolo P | stats_json |
| `goals.saves` | Parate | Portieri | Candidato input Rating Beta (coefficienti **non** chiusi) | FR-SCO-01 | Opzionale / da calibrare | Alto (Beta) | Escludere dalla formula finché non calibrato | stats_json |
| `shots.*` / `passes.*` / `tackles.*` / `duels.*` / `dribbles.*` / `fouls.*` | Stats prestazione | Copertura variabile per lega | Input candidati Rating Beta; pesi versionati post-calibrazione | FR-SCO-01 | Opzionale fino a calibrazione; poi Obbligatorio per componenti scelte | Alto (Beta) | Formula degradata documentata / senza componente | stats_json |
| `cards.yellow` / `cards.red` | Cartellini stats | Live/FT | Cross-check events | FR-SCO-02 | Obbligatorio (controllo) | Alto | Events primari | stats_json |
| `penalty.scored` / `missed` / `saved` / `won` / `commited` | Rigori | Variabile | `missed` → −3; `saved` → +3 portiere; scored già nel gol | FR-SCO-02 | Obbligatorio (`missed`,`saved`) | Bloccante | Se `saved` assente → gap bloccante | stats_json |
| Intero blocco `statistics[]` | Snapshot immutabile input | Post-FT + correzioni | Hash + `provider_snapshot` | FR-DAT-01, FR-OMO-01, FR-AUD-01 | Obbligatorio | Bloccante | Re-fetch; non cancellare ultimo buono | `provider_snapshot`, `player_match_stat` |

### 3.9 `/injuries`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `player.id` | Calciatore | Update ~4h (doc) | Availability | FR-RIN-01, FR-AI-* | Obbligatorio | Alto | Eccezione admin se serve convocazione | `availability` |
| `team.id` / `fixture.id` | Contesto | Per entry | Scope | FR-AI-01 | Opzionale | Medio | Filtro league+season | `availability` |
| `player.type` | Injury / Suspension (doc) | Per entry | Distingue infortunio vs squalifica | FR-RIN-01 | Obbligatorio | Alto | Se manca type → non eleggibile a 6 d’ufficio | `availability` |
| `player.reason` | Dettaglio testuale | Per entry | Display / IA; **non** parsing regolamentare automatico | FR-AI-* | Non affidabile (NLP) | Medio | Mostra raw; no auto-regola | `availability` |

### 3.10 `/transfers`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `player.id` | Calciatore | Storico | Soggetto | FR-ROS-01, FR-MKT-02 | Obbligatorio | Alto | Review admin | `transfer` |
| `date` | Data trasferimento | Per entry | Efficacia membership | FR-ROS-01 | Obbligatorio | Alto | Se ambigua → verifica admin (FR-MKT-02) | `transfer` |
| `teams.in.id` / `teams.out.id` | Club destinazione/origine | Per entry | Uscita dai 5 campionati = Derivato (club out-of-perimeter) | FR-MKT-02 | Obbligatorio | Alto | Admin se loan/N/A | `transfer` |
| `type` | Fee string / Free / Loan / N/A | Per entry | Loan e N/A = **Non affidabile** per auto-svincolo | FR-MKT-02 | Non affidabile (auto) | Alto | Coda admin | `transfer` |

### 3.11 `/standings`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `league.standings[][].team.id` | Riga classifica | Update ~1h | Contesto Analista | FR-AI-02 | Opzionale | Basso | IA senza standing | snapshot |
| `rank` / `points` / `goalsDiff` / `form` / `home` / `away` | Record | Per team | Feature IA | FR-AI-02 | Opzionale | Basso | Null | snapshot |
| Qualsiasi campo standings | — | — | **Mai** input a fantavoto / H2H fantasy | FR-SCO-* | Non affidabile (per scoring) | — | N/A | solo AI snapshot |

### 3.12 `/predictions`

| Campo esterno | Semantica | Disponibilità | Trasformazione interna | FR | Classe | Criticità | Fallback | Persistenza |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `predictions.winner` / `advice` / `percent.*` / `under_over` / goals stimati | Forecast algoritmico provider | Prepartita; ~1h; coverage non universale | Segnale staff IA con rischio/affidabilità | FR-AI-01/02 | Opzionale | Medio | Suggerimento senza predizione | `provider_prediction_snapshot` |
| `comparison.*` / h2h embedded | Contesto | Con prediction | Feature IA | FR-AI-02 | Opzionale | Basso | Ignora | snapshot |
| Qualsiasi prediction | — | — | **Mai** verità sportiva né scoring | FR-SCO-*, Master §15 | Non affidabile (fatto) | — | N/A | snapshot etichettato `signal` |

---

## 4. Tracciabilità esigenze critiche → fonte o gap

| Esigenza critica | FR | Fonte primaria | Gap esplicito? |
| --- | --- | --- | --- |
| Listone 5 campionati, ID stabile, un ruolo P–D–C–A | FR-ROS-01 | `/players`, `/players/squads`, `/teams`, `/leagues` | **Sì:** mapping posizione provider → P/D/C/A e policy listone ufficiale non sono chiuse come tabella definitiva (OQ-01). |
| Generazione turno europeo senza duplicare fixture | FR-TUR-01 | `/fixtures` (`id`, kickoff, league, status) | No gap fonte; regola turno è interna. |
| Kickoff lock per calciatore | FR-TUR-02 | `/fixtures.fixture.date|timestamp` + status | No. |
| Formazione fantasy / moduli / mosse | FR-FOR-*, FR-SUB-01 | Dati utente + minuti/voto da `/fixtures/players` (+ eventi) | Lineup ufficiale **non** è fonte della formazione fantasy. |
| Bonus/malus approvati | FR-SCO-02 | `/fixtures/events` + `/fixtures/players` (penalty/cards/conceded) | **Sì bloccante:** autogol univoco, assist events↔stats, rigore parato, doppia ammonizione (OQ-02…05). |
| Rating FantApperò Beta | FR-SCO-01 | Stats `/fixtures/players` (insieme da calibrare) | **Sì:** coefficienti/soglie ancora Beta; rating provider non usabile come voto (OQ-06). |
| 6 d’ufficio solo se convocato | FR-RIN-01 | `/fixtures/lineups` (+ `/injuries` per esclusioni) | **Sì alto:** lineup spesso tardi/assenti; senza convocazione → eccezione admin (già in FR). |
| Trasferimenti / uscita perimetro | FR-MKT-02, FR-ROS-01 | `/transfers` + squads | **Sì:** Loan/N/A e timing membership (OQ-08). |
| IA consultiva | FR-AI-01/02 | lineups, injuries, predictions, standings, stats aggregati | Predictions/standings opzionali; mai scoring. |

---

## 5. Gap bloccanti vs rischi accettabili

### 5.1 Gap bloccanti (impediscono go-live scoring affidabile)

| ID | Tema | Perché bloccante | Esito richiesto prima del go-live |
| --- | --- | --- | --- |
| G-01 | Autogol | Malus −2; falso positivo = gol +3 errato | Classificazione `Own Goal` stabile su campione 5 campionati |
| G-02 | Assist | Bonus +1; divergenza events↔stats | Regola di riconciliazione deterministica |
| G-03 | Rigore parato | Bonus +3 portiere senza `detail` eventi chiaro in doc pubblica | Campo confermato (`penalty.saved` o equivalente) su JSON reali |
| G-04 | Rigore sbagliato | Malus −3 | `Missed Penalty` e/o `penalty.missed` coerenti |
| G-05 | Chiave anti-duplicazione eventi | FR-DAT-01 / FR-SCO-02 | Schema `provider_event_key` collaudato su live+correzioni |
| G-06 | Minuti e “senza voto” | Soglia e sostituzioni | `games.minutes` affidabile per titolari/sub/recupero |
| G-07 | Coverage stats players sui 5 campionati | Senza stats niente Rating Beta | `coverage.fixtures.statistics_players=true` stagione attiva |
| G-08 | Mapping ruolo listone | Rosa 3P–11D–11C–10A | Tabella posizione→P/D/C/A + override admin versionato |

### 5.2 Rischi accettabili (MVP con mitigation)

| ID | Tema | Mitigation |
| --- | --- | --- |
| R-01 | Lineup ufficiali in ritardo o post-gara | FR-RIN-01: eccezione admin; non presumere convocazione |
| R-02 | `player.injured` booleano rumoroso | Usare `/injuries`; flag solo UX |
| R-03 | Predictions/standings incompleti | IA degrada; gioco continua |
| R-04 | Rating provider assente/null | Conservare null; Rating Beta indipendente |
| R-05 | Transfer `Loan` / `N/A` | Coda admin (FR-MKT-02) |
| R-06 | VAR / correzioni tardive | Stato Provvisorio + re-fetch 0–72h post-FT (Architettura §4.2) |
| R-07 | Quota/piano API | Polling adattivo; ultimo dato buono visibile (NFR/Arch §12); piano e scenari in [`../operations/api_football_polling_plan.md`](../operations/api_football_polling_plan.md) (EP00-04) |
| R-08 | Coefficienti Rating ancora Beta | Formula versionata; no retroattivo su omologati |

---

## 6. Controlli di accettazione EP00-01

| Controllo | Esito |
| --- | --- |
| Ogni dato critico listone/turni/formazione/bonus/Rating/IA ha fonte o gap esplicito | §4 |
| Matrice versionata e leggibile senza codice | questo file in `docs/data/` |
| Nessuna chiave API / payload sensibile | solo path campo e semantica |
| Gap bloccanti ≠ rischi accettabili | §5.1 vs §5.2 |
| Endpoint scope tutti presenti | §2 |
| Nomi campo vs doc v3 / guide ufficiali | validati su documentazione pubblica; **payload reali = EP00-02** |
| Cross-check FR | colonne FR + §4 |

---

## 7. Registro follow-up

I punti aperti operativi per collaudo su JSON reali sono in [`api_football_open_questions.md`](./api_football_open_questions.md) (input card **EP00-02**).

Confine provider / anti-corruption layer: [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md).

Dimensionamento quota e polling (EP00-04): [`../operations/api_football_polling_plan.md`](../operations/api_football_polling_plan.md).
