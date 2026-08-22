# EP12-01 — Suite end-to-end critica

| Metadato | Valore |
| --- | --- |
| Card | EP12-01 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | Tutte le Epic Must (M1–M4) |
| Stima originale | 3–5 giorni |

## Stato implementazione (branch `claude/M5`)

**Implementato il flusso critico completo come singolo test Playwright**
(happy path): registrazione → verifica email (Mailpit) → login → creazione
lega privata → rosa → formazione → risultato → mercato, in
`apps/e2e/tests/registration-to-league.spec.ts`. Verificato in verde due
volte di seguito contro lo stack Docker Compose reale (vedi "Come è stato
verificato").

### Due decisioni architetturali prese durante l'implementazione

La ricognizione preliminare (agente Explore, read-only) ha scoperto due
vincoli reali che rendevano impossibile guidare l'intero flusso da UI così
com'è oggi. In entrambi i casi si è scelto di popolare lo stato via un nuovo
script di seed backend (`backend/src/devtools/seed_e2e_scenario.py`), che
chiama i servizi di dominio reali (mai HTTP, mai UI) — coerente con lo stile
già usato da `backend/src/devtools/seed_ai_managers.py`.

1. **Rosa**: guidare un'asta reale (sessione admin, offerta sigillata,
   chiusura, risoluzione) da Playwright è stato scartato per fragilità/costo,
   come già anticipato dal piano. Lo script di seed assegna i giocatori
   chiamando direttamente `market.assignment.assign_winning_bid` — la stessa
   funzione usata dall'asta reale — così da esercitare ledger crediti,
   ownership e sincronizzazione dello stato di composizione rosa reali, senza
   passare dalla UI dell'asta. Scoperta rilevante durante l'implementazione:
   `FantasyLineupService.save_my_lineup` rifiuta con `roster_not_validated`
   se la rosa non è `VALIDATED`, e la validazione richiede sia le quote di
   ruolo esatte (3P/11D/11C/10A, fisse via `CheckConstraint` su
   `league_rules`) sia **almeno 3 campionati distinti rappresentati in rosa**
   (`FR-ROS-02`, `MIN_ROSTER_COMPETITIONS`). Il dataset fixture
   `backend/tests/fixtures/api_football/` copre un solo campionato/match
   reale (West Ham–Chelsea, provider 39) — insufficiente per 3 campionati.
   Lo script quindi sincronizza il catalogo squadre (`sync_catalog`) sotto
   **tre `competition_provider_id` diversi (39/140/135) riusando lo stesso
   payload `teams.json`**, cosa che collega artificialmente gli stessi club
   reali a tre campionati — non realistico, ma sufficiente a soddisfare il
   vincolo di dominio con dati puramente sintetici, dichiarato nel commento
   del codice. I 35 atleti per squadra sono invece **sintetici** (creati
   dallo script, non dal dataset fixture), con `RoleAssignment.club_id`
   assegnato round-robin fra i club sincronizzati (esclusi West Ham/Chelsea,
   per non farli risultare "già in campo" e quindi bloccati nella
   formazione). Rose fisse riutilizzate fra run (idempotenti, provider_id
   dedicati ≥ 9 100 000) invece di crescere a ogni esecuzione.
2. **Risultato turno**: confermato che il tab "Risultati" in
   `MatchdayPage.tsx` è un placeholder statico e che l'intera pipeline di
   calcolo (`compute_fixture_ratings` → `compute_round_effective_lineups` →
   `compute_round_results` → `compute_league_standings` →
   `homologate_round`) richiede `Permission.GLOBAL_OPERATE`, un ruolo
   operatore piattaforma non ottenibile dal flusso di registrazione
   self-service. Lo script di seed chiama quindi questi servizi direttamente,
   riusando **lo stesso dataset e la stessa sequenza già validata** da
   `backend/tests/integration/leagues/test_scoring_service.py` (fixture
   1035055, campionato 39). Il turno stesso (`FantasyRound` +
   `FantasyRoundFixture` + `LeagueCalendar`/`LeagueCalendarSlot`) è creato
   via ORM diretto anziché tramite `FantasyTurnService.ensure_upcoming_for_league`:
   quel servizio seleziona solo fixture il cui kickoff cade in una finestra
   futura vicina a "adesso", ma la fixture del dataset ha un kickoff storico
   fisso già `FT` (necessario per calcolare un risultato finale
   deterministico) — le due esigenze sono incompatibili con lo stesso turno,
   quindi il turno viene scritto direttamente con `status=OPEN` per restare
   modificabile da UI. **Scoperta di re-run**: `PlayerMatchRating` e il
   "fixture omologato" sono globali per `fixture_id`, non per lega — dopo il
   primo run E2E che omologa il turno, i run successivi (nuove leghe, stesso
   match condiviso) trovano `compute_fixture_ratings` già bloccato da
   `assert_fixture_not_homologated`. Lo script intercetta questo caso
   specifico (`ValidationAuthError` con `code="round_homologated"`) e
   prosegue riusando i voti già calcolati, invece di fallire — verificato
   creando due leghe indipendenti in sequenza (vedi sotto).

Il test Playwright non tocca mai `/asta` né prova a raggiungere un tab
risultati da UI: dopo la creazione della lega chiama
`docker compose run --rm api python -m devtools.seed_e2e_scenario --stage roster ...`,
poi guida la formazione da UI reale, poi chiama lo stage `--stage results`,
poi guida lo svincolo di mercato da UI reale. I due stage sono entrambi
idempotenti (richiamabili più volte senza duplicare lavoro), requisito
esplicito per poterli invocare due volte nello stesso test.

### I 3 stati aggiuntivi (vuoto, errore, permessi insufficienti)

Aggiunti in una sessione successiva, in un file separato
`apps/e2e/tests/critical-flow-states.spec.ts` (non nello stesso file del
flusso positivo, per tenere ogni scenario indipendente e più corto da
leggere/debuggare) con 3 test indipendenti:

1. **Stato vuoto** (`formation-empty`): registrazione → verifica → login →
   creazione lega via UI, **senza invocare lo stage `roster` del seed** —
   nessun turno esiste ancora per la lega, quindi `/formazione` mostra
   direttamente lo stato vuoto reale (non serve popolare nulla apposta:
   `fetchFantasyTurns` ritorna una lista vuota per una lega appena creata).
2. **Stato errore** (`formation-action-error`): stesso setup del flusso
   positivo (stage `roster` del seed per una rosa validata), poi in
   `/formazione` vengono riempiti solo 10 degli 11 slot titolari e si preme
   "Salva formazione": la validazione client-side (`evaluateLineup`,
   pacchetto `@fantappero/contracts`) rifiuta la formazione incompleta
   (`starter_count_invalid`/`missing_athlete`) **prima** di raggiungere il
   backend, mostrando `formation-action-error`. Non è stato possibile
   provocare un rifiuto lato server attraverso l'UI reale (il rendering dei
   dropdown titolari esclude sempre gli atleti già selezionati altrove,
   quindi non è possibile costruire un duplicato via UI; un modulo "non
   valido" non è selezionabile perché il `<select>` offre solo i 7 moduli
   approvati) — la copertura di un rifiuto *server-side* di una formazione
   resta un gap noto (vedi "Rischi e domande aperte").
3. **Permessi insufficienti** (`route-forbidden`): scoperta rilevante durante
   l'implementazione — i permessi `roster:view`/`roster:edit`/`market:view`
   sono concessi a **qualunque** membro di lega (non solo admin, vedi
   `packages/contracts/src/auth.ts`, `LEAGUE_MEMBER_PERMISSIONS`), quindi gli
   stati `formation-forbidden`/`auction-forbidden` documentati nella
   ricognizione preliminare sono **raggiungibili solo in demo mode**
   (`?persona=…&stato=forbidden`), mai da un utente reale autenticato. Il
   gate di permesso reale e testabile da UI è invece quello route-level di
   `RequirePermissions` (`apps/web/src/auth/RequirePermissions.tsx`), usato
   ad es. da `/lega/amministrazione` e `/fantallenatori` (permesso
   `league:admin`, concesso solo al ruolo `OWNER`/`league_admin` della
   lega). Il test quindi: registra due utenti reali via UI in due browser
   context separati (owner e membro — non login/logout ripetuti sulla
   stessa pagina, per non incorrere nel rate limit reale di login,
   5/minuto/IP, `backend/src/auth/service.py`); il membro attiva
   "Disponibile a ricevere inviti alle leghe" dal proprio profilo; l'owner
   lo invita nominativamente dalla directory fantallenatori
   (`/fantallenatori`); il membro accetta l'invito da `/inviti` (flusso di
   invito nominativo reale, `NamedLeagueInviteService`, non un bypass); il
   membro (ora `LeagueMemberRole.MEMBER`, non admin) naviga su
   `/lega/amministrazione` e vede `route-forbidden`.

Verificato in verde **due volte di seguito**, insieme al flusso positivo
esistente, contro lo stesso stack Docker Compose reale (vedi "Come è stato
verificato" sotto per il comando esatto).

### Cosa resta fuori scope

- **Rifiuto formazione lato server**: come sopra, i 3 stati minimi sono
  coperti ma l'errore di formazione testato è client-side; un vero rifiuto
  server-side (es. cutoff turno scaduto, calciatore bloccato) richiederebbe
  manipolare l'orologio del turno seedato, non tentato per limitare lo
  scope.
- **Copertura mobile** (`apps/mobile`): non affrontata, come già segnalato
  come rischio/domanda aperta dal piano.
- **Scambio tra partecipanti** come operazione di mercato post-turno: è
  stato implementato lo svincolo volontario (più semplice, un solo
  partecipante), non lo scambio (richiederebbe una seconda squadra che
  approva via UI, fuori dallo scope minimo "un'operazione di mercato
  post-turno").

### Come è stato verificato

Comandi eseguiti realmente (Windows, Docker Desktop):

```
docker compose build api                       # include backend/src/devtools/seed_e2e_scenario.py nell'immagine
docker compose up -d --force-recreate api worker beat
cd apps/e2e && npm install && npx playwright install chromium
npx playwright test --reporter=list
```

- Verifica isolata dello script di seed (prima di Playwright): due leghe di
  smoke test create via ORM diretto, `--stage roster` poi `--stage results`
  su entrambe in sequenza — confermato `owner_team_status=validated`,
  `away_team_status=validated`, `result_final=True`,
  `homologation_status=homologated` su entrambe; il secondo run ha
  confermato l'intercettazione di `round_homologated` sulla fixture
  condivisa (vedi sopra). Rieseguito `--stage roster`/`--stage results`
  sulla stessa lega una seconda volta: nessuna modifica, output
  `"results already homologated"` (idempotenza confermata).
- Suite Playwright completa (`npx playwright test`, ora 4 test su 2 file —
  flusso positivo + 3 stati): **verde, eseguita due volte di seguito**
  (44.2s e 44.5s), ciascuna con lega/utenti nuovi (nomi/email dinamici), a
  conferma che script di seed e flusso UI sono ripetibili senza stato
  residuo problematico.
- `ruff check` / `ruff format --check` puliti su
  `backend/src/devtools/seed_e2e_scenario.py`.
- **Rate limit di login reale** (`AUTH_RATE_LIMIT_LOGIN_PER_MINUTE=5`,
  `backend/src/auth/service.py`): un run pulito della suite completa esegue
  esattamente 5 login reali (1 nel test vuoto, 1 nell'errore, 2 nel test
  permessi — un browser context per utente, non login/logout ripetuti — 1
  nel flusso positivo), tutti entro la stessa finestra fissa di 60s dato che
  l'intero run impiega ~44s. È quindi esattamente al limite consentito:
  verificato che passa in verde due volte di seguito con lo stack Docker
  Compose reale (redis pulito a ogni riavvio del container), ma un run
  manuale ripetuto a distanza ravvicinata (redis non riavviato) può
  incontrare "Troppi tentativi" se la finestra dei 60s non è ancora scaduta
  — in tal caso va atteso il timeout della finestra o svuotata la chiave
  Redis `auth:rl:login:<ip>` (solo in ambiente locale/test, mai in
  produzione). Non è un bug: è il comportamento reale e voluto del rate
  limiter; il job CI riparte sempre da uno stack pulito quindi non è
  interessato da questo effetto collaterale delle iterazioni manuali locali.
- **Nota ambientale**: in questo ambiente locale, `npx playwright install
  --with-deps chromium` si è bloccato in modo non deterministico durante il
  download (connessione TLS stabilita ma nessun avanzamento) — non
  riproducibile con `curl` sullo stesso URL (13 MB/s, nessun problema). Non
  è stato possibile determinarne la causa esatta nel tempo disponibile
  (sospetto: interferenza locale, non di rete). Aggirato scaricando
  l'archivio via `curl` ed estraendolo manualmente nella cache di Playwright
  attesa. Il job CI (`e2e-critical-flow` in `.github/workflows/ci.yml`) usa
  il comando standard `npx playwright install --with-deps chromium` su
  `ubuntu-latest`, dove il problema non è mai stato osservato e non è atteso
  (ambiente pulito, rete GitHub Actions verso Azure CDN affidabile); se
  dovesse manifestarsi anche lì, il workaround sopra è riproducibile in uno
  step di CI.

### Job CI

Aggiunto `e2e-critical-flow` in `.github/workflows/ci.yml`: avvia
`postgres`, `redis`, `api`, `web`, `mailpit` via `docker compose up -d
--build` (non `make`), installa Playwright e lancia `npm run test:e2e`,
carica il report HTML come artifact (`always()`), stampa i log dei
container in caso di fallimento, poi `docker compose down -v`. **Non è
nell'elenco `needs` di `ci-success`** e gira solo su `workflow_dispatch`
manuale o su push/PR del branch `claude/M5` (`if:` sul job), per non
appesantire la pipeline richiesta su ogni push ordinario a `main`/`dev` —
coerente con il rischio "tempo di esecuzione" già segnalato sotto. Non è
stato eseguito realmente su GitHub Actions in questa sessione (nessun
accesso a un runner reale); verificato solo che lo YAML è sintatticamente
valido (`python -c "import yaml; yaml.safe_load(...)"`) e che i comandi
usati (`docker compose up -d --build ...`, `npm run test:e2e`) sono gli
stessi già validati manualmente sopra.

## Obiettivo e scope

Coprire con test end-to-end il flusso critico completo:
**registrazione → lega → rosa → formazione → risultato → mercato**, con piano, dati di
test, responsabile ed evidenze definiti, e correggere o accettare formalmente ogni
scostamento.

## Stato attuale nel repo (gap)

- **Nessuna suite E2E esiste**: nessuna directory `e2e/`, nessuna dipendenza Playwright o
  Cypress in `apps/web/package.json`, `apps/mobile/package.json` o alla radice.
- Test disponibili oggi sono solo unit/integration:
  - `backend/tests/unit/`, `backend/tests/integration/` (pytest 8.4.1, contro
    `postgres-test` in `compose.yaml`)
  - `apps/web` — vitest (unit/component, no browser reale)
  - `apps/mobile` — `node --test` su un elenco esplicito di file (`package.json` →
    script `test`)
- CI (`.github/workflows/ci.yml`) non ha job E2E.
- Non esiste uno script di seed che popoli uno "scenario E2E completo" (lega con
  partecipanti, asta conclusa, rose assegnate, turno con risultati). Esistono solo seed
  puntuali (`backend/scripts/seed_ai_coaches.py`, `backend/src/devtools/seed_ai_managers.py`).

## Piano d'azione

1. **Scegliere il framework E2E** (vedi Tooling) e aggiungerlo come dipendenza dev in
   `apps/web` (il frontend web è il client primario; valutare se `apps/mobile` richiede
   copertura E2E separata o se il flusso critico è verificabile solo da web in questa
   fase — coerente con "non implementare funzionalità di card successive").
2. **Definire lo scenario end-to-end di riferimento** come sequenza di step verificabili,
   mappata sui moduli backend reali:
   - Registrazione/login (`backend/src/auth`)
   - Creazione lega e ingresso partecipanti (`backend/src/leagues`)
   - Costruzione rosa (asta o inserimento manuale) (`backend/src/fantasy_teams`,
     `backend/src/market`)
   - Impostazione formazione per un turno (`backend/src/fantasy_lineups`)
   - Calcolo/pubblicazione risultato (`backend/src/fantasy_ratings`,
     `backend/src/fantasy_turns`)
   - Un'operazione di mercato post-turno (svincolo o scambio) (`backend/src/market`)
3. **Creare uno script di seed E2E dedicato** (nuovo, in `backend/src/devtools/` o
   `backend/scripts/`, riusando pattern di `seed_ai_managers.py`) che porti il DB di test
   in uno stato "lega pronta al turno N" in modo deterministico e ripetibile, per non
   dover ricostruire lo scenario da zero ad ogni run E2E.
4. **Implementare gli scenari E2E** per i 4 stati richiesti dai test minimi del progetto
   (positivo, vuoto, errore, permessi insufficienti) sul flusso sopra, non solo sul
   percorso felice.
5. **Aggiungere un job E2E dedicato in CI** (`.github/workflows/ci.yml`), separato dagli
   altri job esistenti, che avvii i servizi via `docker compose` (non `make`), esegua il
   seed E2E e lanci la suite.
6. **Collegare le evidenze**: il job CI deve produrre un report/artifact (es. HTML report
   del framework E2E scelto) allegabile alla card, come richiesto dai criteri di
   accettazione.

## Tooling proposto

- **Playwright** (consigliato): supporta TypeScript nativamente (coerente con
  `apps/web`), genera report HTML/trace utilizzabili come evidenza, ha buon supporto CI
  headless in container Docker. Alternativa valutata e scartata per ora: Cypress (meno
  nativo per multi-browser e trace deterministici in CI headless).
- Nessun nuovo servizio infrastrutturale richiesto: Playwright può puntare al `web`
  servito da `docker compose` e all'`api` come backend reale (no mock), in linea con "no
  test del flusso UI positivo/vuoto/errore/permessi insufficienti".

## Dati di test

- Dataset fixture sportivo già esistente (`backend/tests/fixtures/api_football/`) per
  evitare dipendenza dal provider reale durante E2E.
- Utenti/lega dedicati creati dallo script di seed E2E (punto 3), con credenziali di test
  non riutilizzabili in produzione (nessun segreto reale).

## Criteri di accettazione (dalla card)

- Flusso verde su ambiente pulito e dati fixture.
- Evidenze collegate alla card.

## Test minimi richiesti

- Flusso UI positivo (happy path) sull'intera catena registrazione→mercato.
- Flusso UI con stato vuoto (es. lega senza partecipanti, rosa incompleta).
- Flusso UI con errore (es. tentativo di formazione con modulo non valido).
- Flusso UI con permessi insufficienti (es. utente non admin che tenta un'azione riservata).

## Rischi e domande aperte

- Tempo di esecuzione: una suite E2E completa su Docker Compose può essere lenta in CI;
  valutare se farla girare solo su branch `M5`/pre-release invece che su ogni push, per
  non appesantire la pipeline esistente (`ci-success` gate).
- Copertura mobile: `apps/mobile` non ha oggi alcun framework E2E; decidere se è nello
  scope Beta o rimandabile.
- Va verificato puntualmente (fuori scope di questo documento) che EP04-07 e
  EP06-05/06/07 siano davvero implementate, perché lo scenario E2E le attraversa
  indirettamente (formazione, qualità dati).
- Rate limit di login reale (5/minuto/IP): la suite completa esegue esattamente 5 login
  in un run pulito, al limite consentito (dettagli in "Come è stato verificato"). Se in
  futuro si aggiungono altri scenari con ulteriori login, va rivista la strategia (più
  browser context paralleli, riuso di sessioni già autenticate, o alzare il limite negli
  ambienti di test) per non superare la soglia.
- Errore di formazione testato solo lato client: la validazione `evaluateLineup` blocca il
  salvataggio prima che raggiunga il backend, quindi il test "errore" non esercita un
  rifiuto server-side reale (es. cutoff scaduto). Non c'è oggi un modo pulito di provocare
  un rifiuto server-side da UI senza manipolare l'orologio del turno seedato.
