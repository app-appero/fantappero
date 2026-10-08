# Matrice di parità Web/Mobile (Blocco C1)

**Data:** 26/09/2026
**Perimetro:** i 17 flussi minimi elencati dal piano di chiusura Fase 1 (Blocco C), sulle 10 dimensioni richieste da C1: endpoint, campi mostrati, azioni disponibili, permessi, stati (loading/empty/error/success/forbidden), messaggi, deep link, accessibilità, test automatici, prova su dispositivo reale.
**Metodo:** censimento del codice sorgente (`apps/web/src`, `apps/mobile/src`). **Non è una prova su dispositivo reale**: quella resta esplicitamente rimandata a un momento successivo (decisione presa il 26/09/2026), da eseguire fisicamente su browser + emulatore/telefono prima di dichiarare il Blocco C concluso.

## 1. Sintesi

La logica di business (endpoint chiamati, permessi verificati, gestione degli stati loading/empty/error/success/forbidden) è **sorprendentemente ben allineata** flusso per flusso tra le due piattaforme. I problemi reali trovati sono soprattutto **trasversali** (toccano più flussi insieme) o **un disallineamento di prodotto già deciso ma mai propagato**:

| # | Problema | Gravità | Flussi coinvolti |
|---|---|---|---|
| 1 | ~~**ADR-0006 non applicata al mobile**~~ — **CORRETTO il 26/09/2026**: aggiunti su mobile gli stessi flag `SHOW_WAIVER_TAB`/`SHOW_VOLUNTARY_RELEASE`/`SHOW_MARKET_HISTORY` già presenti sul web, tab rinominata "Scambi". Codice sottostante non toccato, stesso principio di ADR-0006. | Risolta | 10 |
| 2 | **Sessione non persistente sul mobile**: il token è tenuto solo in memoria (una `Map` in JS), non in storage sicuro/persistente. Chiudere del tutto l'app forza sempre un nuovo login. | Alta (UX), non è un problema di sicurezza | 2, 8 |
| 3 | **Nessun deep link funzionante sul mobile**: non esiste una configurazione di `linking`/scheme. I campi per accogliere un token da link (reset password, invito, join-lega) esistono nel codice ma non sono mai raggiungibili da un link reale, solo da inserimento manuale. | Alta | 1, 3, 5, 15 |
| 4 | **Verifica email incompleta sul mobile**: la funzione di chiamata API esiste ma nessuna schermata la usa; combinato con il punto 3, un utente che si registra da mobile non ha modo di completare la verifica restando nell'app. | Alta | 1 |
| 5 | **Nessun test end-to-end reale sul mobile**: non esiste Detox/Maestro né alcuna configurazione e2e. I file di test mobile sono quasi tutti verifiche banali (es. "la funzione esiste"), non test di comportamento. | Alta (criterio C2 del piano, non ancora soddisfatto) | trasversale |
| 6 | **Nessuna notifica push sul mobile**: le notifiche si vedono solo aprendo l'app (pull), non arrivano come notifica di sistema. | Media | 15 |
| 7 | Le schermate di amministrazione globale (operatore) sul mobile non hanno un controllo permessi lato client (si affidano solo al 403 del backend), mentre il web mostra un pannello "accesso negato" esplicito prima di provare. Non è un buco di sicurezza (il backend blocca comunque), ma l'esperienza utente diverge. | Bassa | 17 |
| 8 | Su entrambe le piattaforme esiste un endpoint di preferenze-notifica per categoria (`GET/PUT /notifications/preferences`) che **nessuna delle due UI usa** — funzionalità abbandonata simmetricamente, non è un gap di parità. | Info | 15 |
| 9 | **Accessibilità disomogenea su entrambe le piattaforme, più debole nelle schermate amministrative.** Web: buona base nei componenti condivisi (`label`/`htmlFor`, `role="alert"` sugli errori form, `aria-live` su alcuni contatori/stati loading) ma applicata a macchia di leopardo — molti messaggi di successo/errore delle azioni admin non hanno `aria-live`, quindi uno screen reader non li annuncia automaticamente. Mobile: quasi tutta l'accessibilità passa dal componente condiviso `UiStatePanel` (loading/empty/error/success/forbidden); al di fuori di quello, la maggior parte dei pulsanti nelle schermate admin ha solo `testID`, senza `accessibilityLabel`/`accessibilityRole` propri. Non è un gap di parità (il problema è simile su entrambe le piattaforme), ma è un difetto reale da correggere prima del pilota. | Media | 9, 10, 17 (soprattutto) |

## 2. Verdetto per flusso

| # | Flusso | Verdetto | Nota |
|---|---|---|---|
| 1 | Registrazione e verifica email | **Gap** | Mobile non permette di completare la verifica in-app (problema #3+#4) |
| 2 | Login, refresh e logout | **Gap (UX)** | Mobile non ricorda la sessione dopo chiusura completa (problema #2) |
| 3 | Recupero password | **Gap** | Link di reset non funzionante su mobile (problema #3), fallback manuale presente |
| 4 | Creazione lega | Equivalente | |
| 5 | Ingresso con codice | **Parziale** | Web supporta link diretto (`?token=`), mobile solo inserimento manuale del codice |
| 6 | Invito nominativo | Equivalente | |
| 7 | Accettazione/rifiuto invito | Equivalente | |
| 8 | Selezione lega attiva | **Gap (UX)** | Persistenza della scelta non sopravvive alla chiusura app (problema #2) |
| 9 | Rosa e crediti | Equivalente | Import CSV nascosto su entrambe le piattaforme, coerente; accessibilità mobile più debole (problema #9) |
| 10 | Asta/mercato | **Corretto il 26/09/2026** | Vedi problema #1: ADR-0006 ora applicata anche al mobile; accessibilità debole su entrambe (problema #9) |
| 11 | Formazione e lock | Equivalente | Logica di blocco/kickoff condivisa via `@fantappero/contracts`, ben allineata |
| 12 | Turni europei | Equivalente | |
| 13 | Matchup H2H | Equivalente | Flusso con la migliore accessibilità su entrambe le piattaforme (label ARIA costruite ad-hoc, non solo generiche) |
| 14 | Risultati e classifica | Equivalente | |
| 15 | Notifiche | **Gap** | Nessuna push su mobile (problema #6); preferenze per categoria inutilizzate su entrambe |
| 16 | Profilo e privacy | Equivalente | |
| 17 | Funzioni amministrative indispensabili | **Parziale** | Assenza di gate lato client sul mobile per l'admin globale (problema #7); accessibilità la più debole di tutta la matrice su entrambe le piattaforme (problema #9) |

**Colonna "prova su dispositivo reale" (richiesta dal piano):** rimandata di proposito — decisione presa il 26/09/2026 di completare prima l'analisi da codice per tutti i 17 flussi, e affrontare la verifica fisica su device/emulatore in un secondo momento, insieme al resto del Blocco C.

## 3. Dettaglio per flusso

Per ciascun flusso: pagina/schermata, endpoint, permessi, stati gestiti, campi mostrati, azioni disponibili, messaggi reali mostrati all'utente, accessibilità, test automatici. Fonte: censimento diretto del codice (non manuale su device).

### 1. Registrazione e verifica email
- **Web:** `AuthRegisterPage`, `AuthVerifyEmailPage` — `POST /auth/register`, `POST /auth/verify-email`, `POST /auth/resend-verification`. Nessun permesso richiesto. Stati loading/success/error gestiti.
  - Campi: Nome visualizzato, Email, Password, Conferma password.
  - Azioni: "Registrati"; link "Accedi"; dopo successo "Torna al login". Verifica email è automatica al caricamento pagina (nessuna azione utente).
  - Messaggi: validazione "Compila tutti i campi obbligatori."/"Le password non coincidono."; successo = testo dal backend (`response.message`); verifica — loading "Stiamo confermando il tuo indirizzo email…", link mancante "Link di verifica non valido.", errore fallback "Link non valido o scaduto."
  - Accessibilità: label associate via `htmlFor`, errore in `<p role="alert">`; nessun `aria-live` sul messaggio di successo.
  - Test: solo a livello di rendering (`App.auth.test.tsx`), nessun test del token di verifica.
- **Mobile:** `AuthRegisterScreen` (solo registrazione) — `POST /auth/register`. La funzione `verifyEmail()` esiste in `api/auth.ts` ma **nessuna schermata la richiama**.
  - Campi: Nome visualizzato, Email, Password, Conferma password.
  - Azioni: "Registrati", "Torna al login" (post-successo), "Accedi" (link).
  - Messaggi: stesse validazioni testuali del web; successo = testo dal backend.
  - Accessibilità: ogni campo ha `accessibilityLabel` proprio; bottoni con `accessibilityRole="button"` espliciti — leggermente più esplicito del web su questo punto specifico.
  - Test: nessuno.
- **Verdetto:** Gap — vedi problema #1/#4 in sintesi (il gap è funzionale — verifica non completabile — non di dettaglio UI).

### 2. Login, refresh e logout
- **Web:** `AuthLoginPage`, `LogoutButton` — `POST /auth/login|refresh|logout`, `GET /auth/me`, orchestrati da `AuthContext`. `RequireAuth` gate su tutte le route protette.
  - Campi: Email, Password.
  - Azioni: "Accedi", "Password dimenticata?", "Registrati"; "Esci" (logout).
  - Messaggi: errore login = testo dal backend con fallback "Accesso non riuscito."; nessun messaggio esplicito di successo login/logout (solo redirect); `RequireAuth` loading "Stiamo verificando le tue credenziali…".
  - Accessibilità: form con label associate, errore `role="alert"`; `LogoutButton` senza `aria-label` proprio (solo testo "Esci").
  - Test: `AuthContext.test.tsx`, `App.auth.test.tsx`.
- **Mobile:** `AuthScreen`, logout in `ProfileScreen` — stessi 4 endpoint. Sessione **in memoria** (`sessionStorage.ts` usa una `Map`, nessun AsyncStorage/SecureStore): chiusura completa dell'app = logout forzato.
  - Campi: Email, Password (+ riga debug "API: {url}" solo in `__DEV__`).
  - Azioni: "Password dimenticata?", "Accedi", "Registrati"; "Logout" in Profilo.
  - Messaggi: validazione "Inserisci email e password."; errore "Accesso non riuscito."; nessun messaggio di successo esplicito (login o logout).
  - Accessibilità: campi Email/Password con `accessibilityLabel` e bottoni con `accessibilityRole="button"` + label espliciti; il bottone Logout ha solo `accessibilityRole` (nessuna label dedicata).
  - Test: nessuno.
- **Verdetto:** Gap (UX) — problema #2.

### 3. Recupero password
- **Web:** `AuthForgotPasswordPage`, `AuthResetPasswordPage` — `POST /auth/forgot-password|reset-password`. Supporta link diretto con `?token=`.
  - Campi: Forgot: Email. Reset: Password, Conferma password (token letto da URL, non da un campo visibile).
  - Azioni: "Invia link di reset" / "Salva password"; link "Torna al login" / "Vai al login".
  - Messaggi: reset senza token "Link non valido. Richiedi un nuovo reset password."; mismatch "Le password non coincidono."; successo = testo dal backend.
  - Accessibilità: stessa base label/role="alert" degli altri form auth; nessun `aria-live` sul successo.
  - Test: solo rendering.
- **Mobile:** stesse due schermate/endpoint, ma nessun collegamento reale funziona (problema #3): il campo token va incollato a mano.
  - Campi: Forgot: Email. Reset: Token (campo visibile e compilabile a mano — diversamente dal web, qui è un campo esplicito perché non c'è modo di riceverlo da link), Nuova password, Conferma password.
  - Azioni: "Invia link di reset"/"Salva password"; "Torna al login"/"Vai al login" (post-successo).
  - Messaggi: validazione "Inserisci il token ricevuto via email, oppure apri il link completo."/"Le password non coincidono."; successo = testo dal backend.
  - Accessibilità: ogni campo con `accessibilityLabel` (incluso "Token reset", assente sul web perché lì il token non è un campo utente); bottoni con `accessibilityRole="button"`.
  - Test: nessuno.
- **Verdetto:** Gap — utilizzabile ma peggiore sul mobile (richiede di copiare manualmente il token dall'email).

### 4. Creazione lega
- **Web:** `CreateLeaguePage` — `GET /leagues/competitions`, `POST /leagues`. Permesso `league:view`. Stati loading/empty/error/success.
  - Campi: Nome lega, Stagione (sola lettura), elenco campionati con checkbox + contatore "X di Y selezionati" (minimo 3).
  - Azioni: "Seleziona tutto"/"Deseleziona tutto", toggle campionato, "Crea lega privata", "Annulla"; post-successo "Configura la lega"/"Più tardi".
  - Messaggi: "Inserisci un nome per la lega."/"Seleziona almeno 3 campionati."; successo `«{nome}» è pronta per la configurazione. Sei amministratore della lega.`
  - Accessibilità: lista campionati in `<fieldset><legend>Campionati (minimo 3)</legend>`, contatore in `<p aria-live="polite">` (annuncia il numero selezionato in tempo reale) — punto di accessibilità più curato di molti altri flussi web.
  - Test: `CreateLeaguePage.test.tsx`.
- **Mobile:** `CreateLeagueScreen` — stessi endpoint e permesso.
  - Campi: Nome lega, Stagione (sola lettura, con hint), elenco campionati con `Switch` + nome/paese, contatore selezionati.
  - Azioni: "Seleziona tutto"/"Deseleziona tutto", toggle switch, "Crea lega privata".
  - Messaggi: stesse validazioni testuali del web.
  - Accessibilità: righe campionato con `accessibilityRole="checkbox"` + `accessibilityState={{checked}}`; manca l'equivalente dell'annuncio live del contatore selezionati che il web ha.
  - Test: presente ma banale (verifica solo che l'export sia una funzione).
- **Verdetto:** Equivalente.

### 5. Ingresso con codice
- **Web:** `JoinLeaguePage` — `POST /leagues/inviti/accetta`. Supporta `?token=` da link diretto.
  - Campi: Codice invito (nascosto se il token arriva da link).
  - Azioni: "Entra nella lega"; post-successo "Apri home lega".
  - Messaggi: "Inserisci un codice invito."; successo `Ora fai parte di {leagueName}.` (variante "Sei già nella lega" se già membro).
  - Accessibilità: nessun `aria-live` dedicato oltre al default del pannello di stato condiviso.
  - Test: `JoinLeaguePage.test.tsx`.
- **Mobile:** `JoinLeagueScreen` — stesso endpoint, accetta un parametro token via navigazione interna ma non da link esterno reale (problema #3).
  - Campi: Codice invito (o pannello "Link invito pronto" se il token arriva da navigazione interna).
  - Azioni: "Entra nella lega"; post-successo "Apri home lega".
  - Messaggi: identiche a web nel testo (stesse chiavi di traduzione concettuale); hint aggiuntivo "Ingresso solo su invito: usa il link ricevuto oppure inserisci il codice."
  - Accessibilità: bottone submit con `accessibilityLabel="Entra nella lega"` esplicito, più specifico del web su questo punto.
  - Test: nessuno.
- **Verdetto:** Parziale — la differenza è solo nel canale (link vs. codice manuale), non nella logica.

### 6. Invito nominativo
- **Web:** `ManagerDirectory`/`ManagerDirectoryPage` — `GET .../fantallenatori`, `POST .../inviti-nominativi`. Permesso `league:admin`. Stati completi incl. "lega piena".
  - Campi: filtri (ricerca nome, tipologia, disponibilità); per fantallenatore: avatar, nome, badge tipo/disponibilità, "dal {data}", riepilogo storico; profilo esteso con tabella piazzamenti.
  - Azioni: filtri con debounce 300ms, click su nome → profilo, "Invita"/stato bottone, paginazione, "Riprova".
  - Messaggi: successo `Invito inviato a {nome}.` o `{nome} è entrato automaticamente nella lega.`; errori specifici per ogni causa (non accetta inviti / già invitato / già in lega / lega piena).
  - Accessibilità: sezione con `aria-labelledby`, link profilo con `aria-label` dinamico (`Apri il profilo di {nome}`), tabella piazzamenti con `<caption>` nascosta e `<th scope="col">` — tra i flussi web meglio curati.
  - Test: `ManagerInvites.test.tsx`.
- **Mobile:** `CoachDirectoryPanel`/`ManagerDirectoryScreen` — stessi endpoint e permesso.
  - Campi: avatar/iniziale, nome, tipo, disponibilità, "dal {data}", riepilogo storico; hint posti disponibili.
  - Azioni: tap identità → profilo, "Invita"/"Già invitato"/"Indisponibile", "Ricarica".
  - Messaggi: stesso set testuale del web negli errori specifici; messaggio lega piena identico nel contenuto.
  - Accessibilità: pressable "Apri profilo" con `accessibilityLabel` dinamico equivalente al web; il bottone "Invita" invece **non** ha una label dedicata (solo `accessibilityRole`), a differenza del corrispondente link-profilo.
  - Test: `directoryDemo.test.ts` risulta legato a un helper demo/wireframe, non alla schermata reale.
- **Verdetto:** Equivalente (a parità di endpoint/permessi/stati/messaggi; differenza solo nella qualità dei test e in un dettaglio di accessibilità minore, non nel comportamento).

### 7. Accettazione/rifiuto invito
- **Web:** `ReceivedInvitesPage` — `GET/POST .../inviti-ricevuti...`. Permesso `league:view`. Badge conteggio in sidebar.
  - Campi: nome lega, "Invito nominativo per {destinatario}".
  - Azioni: "Accetta"/"Rifiuta" per invito, "Riprova".
  - Messaggi: successo `Sei entrato in {leagueName}.` / "Invito rifiutato."; errori specifici (capienza massima, invito già gestito).
  - Accessibilità: nessun `aria-label` sui bottoni Accetta/Rifiuta oltre al testo visibile.
  - Test: in `ManagerInvites.test.tsx`.
- **Mobile:** `ReceivedInvitesScreen` — stessi endpoint/permesso, badge in drawer (aggiornato solo all'apertura, nessun polling).
  - Campi: nome lega, etichetta statica "Invito nominativo".
  - Azioni: "Accetta"/"Rifiuta" per invito.
  - Messaggi: `Hai accettato l'invito a {leagueName}.` / `Hai rifiutato l'invito a {leagueName}.` — stesso contenuto informativo del web, formulazione leggermente diversa.
  - Accessibilità: bottoni Accetta/Rifiuta senza label dedicata, come sul web.
  - Test: demo non rappresentativi (`inviteDemo.test.ts`).
- **Verdetto:** Equivalente.

### 8. Selezione della lega attiva
- **Web:** `LeagueSelector` in header, stato in `AuthContext`, persistito in `sessionStorage`. Nessun endpoint dedicato (riusa `GET /leagues/mine`).
  - Campi: select con elenco leghe, badge stato lega, countdown lock se presente.
  - Azioni: cambio lega da select; "Riprova" se il caricamento fallisce; link rapidi "Crea lega"/"Unisciti con codice".
  - Messaggi: errore caricamento mostrato direttamente dal backend/contesto, nessun testo fisso.
  - Accessibilità: select con label "Lega attiva" associata; errore in `<p role="alert">`.
  - Test: nessuno dedicato.
- **Mobile:** `LeagueSelector` equivalente, stesso pattern di stato e persistenza — ma la persistenza non sopravvive alla chiusura completa dell'app (stesso problema #2 della sessione).
  - Campi: chip per ogni lega (etichetta = nome), label "Lega attiva".
  - Azioni: tap su chip per cambiare lega; nell'header: "Crea lega", "Unisciti con codice", menu, logout.
  - Messaggi: nessuno specifico (componente puramente di selezione, come sul web).
  - Accessibilità: gruppo con `accessibilityRole="radiogroup"`, ogni chip `accessibilityRole="radio"` + `accessibilityState={{selected}}` + label — più esplicito del web su questo singolo componente (che usa una semantica HTML nativa di `<select>`, comunque accessibile ma meno "annunciata" nel dettaglio).
  - Test: nessuno dedicato.
- **Verdetto:** Gap (UX), stessa causa del punto 2 — la sola persistenza cambia, non l'interazione.

### 9. Rosa e crediti
- **Web:** `RosterPage` + sottocomponenti — famiglia estesa di endpoint rosa/crediti/CSV/storico. Permessi `roster:view`/`roster:edit`/`league:admin`. Import/export Excel rose visibile agli admin (`roster-excel-import`).
  - Campi: riepilogo composizione per ruolo, tabelle rosa (calciatore/club/crediti/slot), pannello crediti/aggiustamento, listone admin, storico (intervalli possesso, ledger, snapshot per turno).
  - Azioni: assegna/rimuovi calciatore, modifica prezzo, aggiusta crediti, assicura squadre, rosa random IA, snapshot turno, (import CSV se riattivato).
  - Messaggi: validazioni puntuali per ogni azione (es. "Nessuno slot libero…", "Inserisci crediti acquisto validi (minimo 1)."), conferme con dettaglio numerico (es. `Movimento registrato. Nuovo saldo: {n} crediti.`).
  - Accessibilità: input prezzo con `aria-label` dinamico per riga, tab listone con `aria-label`; **nessun `aria-live`** sui messaggi di successo/errore delle azioni admin.
  - Test: `RosterPage.test.tsx`.
- **Mobile:** `RosterScreen` — stessi endpoint e permessi, stesso import CSV nascosto con lo stesso pattern.
  - Campi/Azioni/Messaggi: stesso contenuto informativo del web, stessa formulazione dei messaggi di validazione ed esito (verificato testo per testo, coincide).
  - Accessibilità: **più debole del web** — quasi tutti i pulsanti (Assegna/Rimuovi/Aggiusta crediti/tab) hanno solo `testID`, senza `accessibilityRole`/`accessibilityLabel` propri; si affidano interamente a `UiStatePanel` per gli stati.
  - Test: solo su logica di supporto (`fantasyTeams.test.ts`).
- **Verdetto:** Equivalente nel comportamento; accessibilità mobile più debole (problema #9).

### 10. Asta/mercato
- **Web:** `MarketHubPage` (tab Rosa/Asta/Scambi — tab "Svincolati" nascosta: `SHOW_WAIVER_TAB = false` per ADR-0006), `AuctionHubPage`, `AuctionLivePage`, `WaiverPage`, `MarketPage` (rinominata "Scambi"; "Svincolo volontario"/"Storico mercato" nascosti). Permesso `market:view`, admin `market:manage`/`league:admin`.
  - Campi: stato sessione, offerte, form apertura/chiusura, listone filtrato per ruolo; live: modalità chiamata, lotto corrente, storico rilanci; scambi: rosa propria/destinatario, giocatori offerti/richiesti, crediti, scadenza, stato proposta.
  - Azioni: crea/chiudi/risolvi sessione, invia/ritira offerta, chiama/rilancia/aggiudica/salta (live), proponi/accetta/rifiuta/controproponi/approva scambio.
  - Messaggi: esiti risoluzione (`{nome}: assegnato per {importo} crediti` / "spareggio aperto" / "non assegnato"), messaggi di turno live (`Tocca a {nome}: aspetta il tuo turno…`), messaggi di rosa piena nel modal scambio.
  - Accessibilità: `<fieldset><legend>` per lista di chiamata sequenziale, checkbox scambio in `<label>` nativa; **nessun `aria-live`** sul countdown lotto o sugli aggiornamenti di polling.
  - Test: `AuctionPage(.real).test.tsx`, `WaiverPage(.real).test.tsx`, `MarketPage.real.test.tsx`.
- **Mobile:** `AuctionHubScreen`, `WaiverScreen`, `MarketScreen`. **Aggiornato il 26/09/2026**: stessi flag `SHOW_WAIVER_TAB`/`SHOW_VOLUNTARY_RELEASE`/`SHOW_MARKET_HISTORY`, tab rinominata "Scambi".
  - Campi/Azioni/Messaggi: stesso contenuto informativo e stessa formulazione dei messaggi chiave del web (bid non aperto, esiti risoluzione, modal rosa piena — testo pressoché identico).
  - Accessibilità: **la più debole di tutta la matrice su mobile** — pressoché nessun controllo (Invia offerta, Chiama, Rilancia, Accetta/Rifiuta scambio) ha `accessibilityRole`/`accessibilityLabel` proprio, solo `testID`.
  - Test: nessuno dedicato (nessuno copriva le sezioni ora nascoste, coerente).
- **Verdetto:** Corretto il 26/09 per il gap ADR-0006 (era il problema #1, il più rilevante trovato); resta l'accessibilità più debole sul mobile per questo flusso specifico (problema #9).

### 11. Formazione e lock
- **Web:** `FormationPage` — endpoint formazione/bozza/copia/migliore/countdown. Permessi `roster:view`/`roster:edit`. Logica di blocco condivisa via `@fantappero/contracts`.
  - Campi: badge gestione automatica/IA, modulo, mosse tattiche rimanenti, campo da gioco con titolari, panchina con ordine ingresso.
  - Azioni: cambio modulo, assegnazione titolare, riordino panchina, copia formazione precedente, applica migliore, salva bozza/formazione.
  - Messaggi: lock `"Uno o più calciatori non sono più modificabili: la loro partita è già iniziata."`; auto-risoluzione con motivo specifico (bozza/turno precedente/fallback zero); conferme di salvataggio.
  - Accessibilità: `<div role="alert">` sui problemi di validazione formazione, selettore slot con `aria-expanded`/`role="listbox"`, select ordine panchina con `aria-label` dinamico, campo da gioco con `pitchAriaLabel` — tra i flussi web più curati.
  - Test: `FormationPage.test.tsx`, `useLockCountdown.test.tsx`, `LockCountdown.ticking.test.tsx`.
- **Mobile:** `FormationScreen` — stessi endpoint/permessi, stessa libreria condivisa per la logica di blocco (comportamento garantito by design, non solo per somiglianza).
  - Campi/Azioni/Messaggi: stesso contenuto informativo, stessa formulazione dei messaggi di lock e auto-risoluzione, stessa etichettatura degli esiti IA admin.
  - Accessibilità: il picker ordine panchina ha `accessibilityLabel`/`accessibilityRole` espliciti (equivalente al web); il resto dei controlli (modulo, selezione titolare, salva) ha solo `testID`.
  - Test: nessuno dedicato lato mobile (la logica è testata a monte, nel pacchetto condiviso).
- **Verdetto:** Equivalente — è il flusso meglio allineato, grazie al codice di regole condiviso tra le due app.

### 12. Turni europei
- **Web:** `MatchdayPage` (tab "Turni europei"), `FixtureDetailPage`, admin `AdminTurniPage`/`LeagueCalendarPanel`. Permesso `matchday:view`, admin `league:admin`/operatore globale.
  - Campi: elenco turni, dettaglio (fixtures raggruppate per competizione, stato feed provider), sezione "Partite da aggiornare"; dettaglio partita: formazioni, timeline eventi.
  - Azioni: cambio tab/turno, click su partita, admin "Escludi partita", azioni massive turni (sincronizza, calcola giornata, ricalcola storico con motivo obbligatorio).
  - Messaggi: empty turni con spiegazione del prerequisito rose; lock latch `"Un rinvio o un cambio orario non sblocca le partite il cui kickoff originale è già trascorso…"`; esiti azioni massive con conteggi numerici.
  - Accessibilità: sezione timeline con `aria-labelledby`, link partita con `aria-label` descrittivo (`{home} contro {away}, dettaglio partita`); nessun `role="alert"` sugli errori delle azioni massive admin.
  - Test: `MatchdayPage.test.tsx`, `FixtureDetailPage.test.tsx`, `AdminTurniPage.test.tsx`, `LeagueCalendarPanel.test.tsx`.
- **Mobile:** `MatchdayScreen` (tab "Turni europei"), `FixtureDetailScreen`, azioni admin inline.
  - Campi/Azioni/Messaggi: stesso contenuto informativo, stesso testo del messaggio di lock latch, stessa struttura del dettaglio partita (formazioni + timeline).
  - Accessibilità: il link fixture nella lista ha `accessibilityLabel` equivalente al web (`{home} contro {away}, dettaglio partita`); il resto (tab, escludi) ha solo `testID`.
  - Test: nessuno dedicato.
- **Verdetto:** Equivalente.

### 13. Matchup H2H
- **Web:** `MatchdayH2HPanel`, `MatchupDetailPage` — `GET .../calendario/h2h`, `.../scontri/{slotId}`. Permesso `matchday:view`.
  - Campi: meta giornata (scontri/riposi), per scontro: squadre, stato, gol fantasy e punti fantasy etichettati distintamente; dettaglio: formazioni entrambe le squadre con punteggio per giocatore.
  - Azioni: selezione giornata, click su scontro, "Ricarica", "Torna al calendario".
  - Messaggi: empty calendario non confermato (copy diversa per admin vs. membro), caso "bye" (`{team} è a riposo in questa giornata.`), formazione assente.
  - Accessibilità: link scontro con `aria-label` costruito ad-hoc da un helper condiviso (`h2hResultAriaLabel`), non generico; `<dl>/<dt>/<dd>` semantici per Gol/Punti — il flusso con l'accessibilità più curata di tutto il web.
  - Test: `MatchdayH2HPanel.test.tsx`.
- **Mobile:** stessa coppia di schermate/endpoint, stessa gestione del caso "bye".
  - Campi/Azioni/Messaggi: stesso contenuto informativo, stessa distinzione Gol Fantasy/Punti Fantasy, stesso messaggio "bye" e stesso empty differenziato admin/membro.
  - Accessibilità: la riga scontro usa lo stesso helper condiviso `h2hResultAriaLabel` per costruire la label — **identico al web**, non solo simile, perché il codice è condiviso.
  - Test: nessuno dedicato lato mobile.
- **Verdetto:** Equivalente — insieme al flusso 11, il meglio allineato di tutta la matrice, anche in accessibilità.

### 14. Risultati e classifica
- **Web:** `StandingsPage` — `GET .../classifica`. Permesso `matchday:view`.
  - Campi: tabella classifica (Pos., Squadra, G, Pt, GF:GS, FP:FS), evidenziazione riga utente, data ultimo aggiornamento.
  - Azioni: click su nome manager (solo admin) → profilo; "Riprova".
  - Messaggi: empty nessuna lega/classifica non pronta con spiegazione del motivo ("si aggiorna quando i risultati diventano finali").
  - Accessibilità: tabella con caption e intestazioni scope-annotate (nel componente condiviso `StandingsTable`).
  - Test: `StandingsPage.real.test.tsx`.
- **Mobile:** `StandingsScreen` — stesso endpoint/permesso, stessa evidenziazione della propria squadra.
  - Campi/Azioni/Messaggi: stessa struttura tabellare e stesso testo dei messaggi vuoti.
  - Accessibilità: nome squadra cliccabile (solo admin) con `accessibilityLabel` esplicito (`Apri il profilo del fantallenatore di {team}`), equivalente al web.
  - Test: nessuno.
- **Verdetto:** Equivalente.

### 15. Notifiche
- **Web:** `NotificationCenter` in header — `GET/POST /notifications...`. Nessun permesso oltre l'autenticazione.
  - Campi: badge contatore non lette, lista (categoria, titolo, corpo, timestamp).
  - Azioni: apri/chiudi pannello, click su notifica (segna letta + naviga a `deepLink` interno), "Segna tutte come lette".
  - Messaggi: "Caricamento…", "Nessuna notifica".
  - Accessibilità: trigger con `aria-label="Notifiche"`/`aria-expanded`/`aria-haspopup`, chiusura con Escape gestita esplicitamente; **nessun `aria-live`** per il contatore che cambia o per nuove notifiche.
  - Test: `NotificationCenter.test.tsx`.
- **Mobile:** `NotificationsScreen` — stessi endpoint base. **Nessuna notifica push** (nessuna libreria installata, nessuna registrazione device). Deep-link interno mappato solo per `/inviti`, inutilizzabile da una vera notifica di sistema (stesso motivo del problema #3).
  - Campi/Azioni/Messaggi: stesso contenuto (categoria/titolo/corpo/data), "Segna tutte lette", messaggio vuoto equivalente.
  - Accessibilità: ogni card notifica ha `accessibilityLabel` che include lo stato "non letta" (`{title}, non letta`) — più esplicito del web su questo punto.
  - Test: nessuno.
- **Verdetto:** Gap — problema #6 (assenza di push, non la UI in sé che è equivalente).

### 16. Profilo e privacy
- **Web:** `ProfilePage` — profilo, avatar, consenso policy, export/cancellazione account con frase di conferma.
  - Campi: avatar, nome, email (sola lettura), lingua, fuso orario, notifiche email/push, silenzio notifiche (ore), disponibilità inviti, stato consenso policy.
  - Azioni: carica/rimuovi avatar, salva preferenze, aggiorna disponibilità, accetta policy, esporta dati, elimina account (password + frase di conferma).
  - Messaggi: validazione silenzio notifiche, conferme puntuali per ogni azione, frase di conferma eliminazione (`Digita "{FRASE}" per confermare.`).
  - Accessibilità: campi in `<fieldset><legend>`, checkbox con `<label>` nativa, errore form in `role="alert"`; avatar con `alt=""` (decorativo, corretto).
  - Test: `ProfilePage.test.tsx`.
- **Mobile:** `ProfileScreen` — stessi endpoint e stessa frase di conferma per la cancellazione account.
  - Campi/Azioni/Messaggi: stesso set di campi e stessa formulazione dei messaggi (verificato, coincide quasi parola per parola con il web).
  - Accessibilità: alcuni campi con `accessibilityLabel` proprio (nome, ore silenzio), ma i bottoni azione (Salva, Esporta, Elimina, Logout) hanno solo `accessibilityRole`, senza label dedicata — leggermente meno curato del web su questo aspetto specifico.
  - Test: presente ma banale (verifica solo costanti).
- **Verdetto:** Equivalente.

### 17. Funzioni amministrative indispensabili
- **Web:** `LeagueAdminPage` (+ pannelli), sezione operatore globale (`AdminDashboardPage`, `AdminUsersPage`, `AdminLeaguesPage`, `AdminListonePage`, `AdminTurniPage`) — gate esplicito `RequireGlobalOperator` con pannello "accesso negato" dedicato.
  - Campi: regolamento lega, elenco partecipanti, inviti (codice/link), pannello eliminazione; lato piattaforma: conteggi, ricerca utenti/leghe, listone con progresso refresh.
  - Azioni: salva regolamento, trasferisci admin/rimuovi partecipante, genera/conferma calendario, genera/copia/revoca invito, elimina lega (con checkbox); piattaforma: promuovi/revoca operatore, aggiorna listone, azioni massive turni.
  - Messaggi: conferme dettagliate con conteggi numerici per ogni azione massiva, messaggio esplicito "copia ora, non sarà più mostrato" per codice/link invito, protezione "non puoi revocare l'ultimo operatore".
  - Accessibilità: sezioni con `aria-labelledby`, stepper lifecycle con `aria-current="step"`, fieldset con legend per i gruppi di opzioni regolamento; **nessun `aria-live`** sui messaggi di esito delle azioni massive admin — il punto più debole del web in accessibilità.
  - Test: `LeagueAdminPage.test.tsx`, `LeagueSeasonPanel.test.tsx`, `AdminTurniPage.test.tsx`, `App.admin.test.tsx`.
- **Mobile:** `LeagueAdminScreen` (gate `league:admin` presente, equivalente), schermate admin globali (`AdminDashboardScreen` e affini) **senza controllo permessi lato client** — si affidano al 403 del backend, mostrato solo in `AdminDashboardScreen`.
  - Campi/Azioni/Messaggi: stesso contenuto informativo e stessa formulazione dei messaggi di esito (conteggi numerici identici nella struttura al web).
  - Accessibilità: **il punto più debole di tutta la matrice mobile** — unica eccezione è il checkbox di conferma eliminazione lega (`accessibilityRole="checkbox"` + label esplicita); tutto il resto (Salva, Genera, Copia, Promuovi/Revoca, azioni massive turni) ha solo `testID`.
  - Test: solo `leagueDeleteHelpers.test.ts` (helper puro).
- **Verdetto:** Parziale — problema #7 (gate lato client mancante) e accessibilità la più debole su entrambe le piattaforme (problema #9), ma nessuna funzionalità mancante.

## 4. Prossimi passi proposti (da confermare uno per uno prima di intervenire)

In ordine di impatto:

1. ~~Applicare ADR-0006 anche al mobile~~ — **fatto il 26/09/2026**.
2. Rendere la sessione mobile persistente oltre la chiusura dell'app (problema #2).
3. Configurare un vero `linking`/scheme sul mobile per abilitare i link di reset password, invito e join-lega (problema #3), propedeutico anche al punto 4.
4. Aggiungere una schermata di verifica email sul mobile (problema #4).
5. Introdurre almeno un test end-to-end reale su emulatore/device per il mobile (criterio C2 del piano, problema #5).
6. Valutare l'introduzione di notifiche push (problema #6) — richiede una decisione di prodotto, non solo tecnica.
7. Allineare l'esperienza del gate admin globale sul mobile (problema #7) — priorità bassa.
8. Aggiungere `aria-live`/`accessibilityLabel` sui messaggi di esito delle azioni amministrative (problema #9) — priorità bassa/media, tocca entrambe le piattaforme.
9. Eseguire la prova su dispositivo reale (browser + emulatore/telefono) per tutti i 17 flussi, usando questa matrice come checklist — rimandata di proposito, da fare prima di dichiarare il Blocco C concluso.

**Nota:** i punti 2, 5 e 6 comportano scelte di infrastruttura/prodotto (storage sicuro, pipeline e2e, servizio di push) che vanno discusse, non solo implementate.
