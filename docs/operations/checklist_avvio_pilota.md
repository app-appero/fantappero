# Checklist di avvio del pilota

Da percorrere **in ordine, prima di invitare il primo tester**. Ogni voce ha un esito:
`[x]` verificato · `[ ]` da fare · «rischio accettato» = deciso dal decision owner.
Chi controlla: **Claude** = si verifica dal codice/CI · **Rosario** = serve accesso a
Railway, Google, Resend, telefono o casella email.

Stato aggiornato al 04/11/2026.

## 1. Codice e versione

- [x] CI verde su `main` (run sul commit del 03/11 in success: lint, test Python e JS, migrazioni,
  gitleaks, SAST). — Claude. *Ricontrollare sul commit che si congela.*
- [x] Commit congelato `6599eb2` (CI verde) e tag **`pilota-1`** pubblicato su GitHub da Rosario il
  05/11/2026. Regole dei prossimi tag: vedi `release_pilota_regole.md`. — Claude + Rosario
- [x] Backend su Railway (API **e** worker) alla versione del tag. Confermato da Rosario il 05/11/2026. — Rosario
- [x] Sito web alla stessa versione del backend. Confermato da Rosario il 05/11/2026. — Rosario
- [ ] App Android costruita da quel commit e installata sul telefono di prova. — Rosario

## 2. Configurazione in produzione (Railway)

- [x] `AUTH_EMAIL_REGISTRATION_ENABLED=false` sull'API (solo Google). — Rosario
- [x] Client ID Google valido per web **e** app (accesso riuscito da entrambi). — Rosario
- [x] Volume persistente collegato all'API: `api-volume`, mount path `/data/avatars`, 5 GB, regione
  US West (verificato da Rosario su Railway il 04/11/2026). `AVATAR_STORAGE_PATH` non serve
  (default `/data/avatars`); gli allegati delle segnalazioni vanno in `feedback-private` dentro
  lo stesso volume.
- [ ] (Facoltativo) Backup del volume `api-volume`: oggi nessuna copia e nessuna pianificazione;
  avatar e allegati sono persistenti ma non copiati. Rientra nel rischio «restore non dimostrato»
  accettato per il pilota. — Rosario
- [x] `API_FOOTBALL_KEY` presente sul backend e quota giornaliera sufficiente per il periodo. —
  Rosario
- [x] Notifiche push funzionanti sull'app Android (ricevute, confermato da Rosario il 04/11/2026).
- [x] Nessun segreto nel repository: i soli ritrovamenti sono i falsi positivi in
  `.gitleaksignore`; il valore di `API_FOOTBALL_KEY=` in `infra/local/.env.example` è un testo
  segnaposto, non una chiave (verificato il 04/11/2026). Confermato da Rosario.

## 3. Email e contatto

- [x] Decisione del 04/11/2026: **il pilota parte senza email** (dominio Resend non verificato).
  Nessun tester riceve email; restano le notifiche in app e le push Android. Verificare la
  verifica dominio Resend prima di riattivare registrazione/recupero con email. — Rosario
- [x] La casella **info@globetrotta.it** riceve (confermato da Rosario il 04/11/2026): è il
  contatto dell'informativa per copia dati ed eliminazione.

## 3b. Accesso riservato ai tester

- [ ] Rilascio `pilota-2` con la modalità test (backend con migrazione `c4d8e1a7b932`, sito, app) e
  prova: con la modalità attiva un account Google non in lista vede «Non autorizzato». — Claude + Rosario
- [ ] Aggiunti i tester (email Google) e **attivata la modalità test** prima di mandare gli inviti.
  Vedi `modalita_test.md`. — Rosario

## 4. Prova completa con un account Google nuovo

Da fare sia sul **web** sia nell'**app**:

- [x] Accesso con Google; nel profilo risulta «Hai accettato l'informativa privacy». — Rosario
- [x] Ingresso in una lega con un invito. — Rosario
- [x] Mercato e formazione. — Rosario
- [x] Partita con voti visibili. — Rosario
- [x] «Segnala un problema» con una foto; la segnalazione compare nel pannello operatore. —
  Rosario
- [x] Pannello operatore → «Torna all'app» esce correttamente (fix del 03/11). — Rosario
- [x] Eliminazione account scrivendo `ELIMINA`. — Rosario

Prova completata e confermata da Rosario il 04/11/2026 (web e app).

## 5. Dati e leghe

- [x] Voti dei turni calcolati (ricalcolo eseguito). — Rosario
- [ ] Le leghe le creano e le configurano i **tester stessi** (l'amministratore di ogni lega:
  crea la lega, invita i partecipanti, completa rose e calendario; la stagione parte in
  automatico). Compito di Rosario solo **scegliere gli amministratori** e verificare, dopo gli
  inviti, che le leghe rientrino nel protocollo (3-5 leghe, 6-12 partecipanti ciascuna, un
  amministratore ciascuna). — Rosario
- [x] Protocollo del pilota (dimensione e durata: 3-5 leghe da 6-12 partecipanti, almeno 28 giorni
  e 4 turni per lega, una sola coorte) ratificato dal decision owner il 04/11/2026, senza
  modifiche. Le **soglie di successo** (sezione metriche di `beta_pilot_gate.md`) restano da
  ratificare. — Rosario

## 6. Decisioni già prese

- [x] Informativa privacy v. 2026-11 approvata il 04/11/2026; contatto info@globetrotta.it.
- [x] Restore non dimostrato: **rischio accettato per il pilota** (04/11/2026); da rifare prima di
  aprire oltre il pilota. Vedi `registro_requisiti_fase1.md`, blocco E2.
- [x] Pilota solo Google; minorenni esclusi (selezione manuale dei partecipanti).

## 7. Dopo il lancio

- [x] Log di Railway (API e worker): li guardano **insieme Rosario e Claude** (decisione del
  04/11/2026). Claude controlla solo quando Rosario lo chiede (o con un controllo pianificato,
  se attivato): serve concordare i momenti, per esempio a fine giornata e dopo ogni segnalazione.
- [x] Canale per i tester: info@globetrotta.it; risposta **entro 2 giorni lavorativi** (decisione
  del 04/11/2026). Da comunicare ai tester insieme all'invito.
- [x] Piano se qualcosa si rompe: sospendere gli inviti, avvisare i tester, **tornare al tag
  precedente** (decisione del 04/11/2026; vedi `pilot_incident_runbooks.md`). Con il primo tag
  `pilota-1` non esiste ancora un precedente: in quel caso si sospendono gli inviti e si corregge
  in avanti.
- [x] Controllo a 24 ore dal primo invito: lo fanno insieme Rosario e Claude (errori nei log,
  segnalazioni arrivate, push consegnate).

## Limiti noti da dire ai tester

- iPhone: solo sito web (niente app né notifiche push), iOS rimandato alla Fase 2.
- Possibili bug, interruzioni e, in casi eccezionali, perdita di dati (scritto nell'informativa).
