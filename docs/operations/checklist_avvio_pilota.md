# Checklist di avvio del pilota

Da percorrere **in ordine, prima di invitare il primo tester**. Ogni voce ha un esito:
`[x]` verificato · `[ ]` da fare · «rischio accettato» = deciso dal decision owner.
Chi controlla: **Claude** = si verifica dal codice/CI · **Rosario** = serve accesso a
Railway, Google, Resend, telefono o casella email.

Stato aggiornato al 04/11/2026.

## 1. Codice e versione

- [x] CI verde su `main` (run sul commit del 03/11 in success: lint, test Python e JS, migrazioni,
  gitleaks, SAST). — Claude. *Ricontrollare sul commit che si congela.*
- [ ] Scelto il commit da congelare e creato il tag (es. `pilota-1`); da lì le modifiche entrano
  in produzione solo se decise. — Claude + Rosario
- [ ] Backend su Railway (API **e** worker) alla versione del tag. — Rosario
- [ ] Sito web alla stessa versione del backend. — Rosario
- [ ] App Android costruita da quel commit e installata sul telefono di prova. — Rosario

## 2. Configurazione in produzione (Railway)

- [x] `AUTH_EMAIL_REGISTRATION_ENABLED=false` sull'API (solo Google). — Rosario
- [x] Client ID Google valido per web **e** app (accesso riuscito da entrambi). — Rosario
- [ ] Volume persistente collegato al servizio API con **mount path `/data`** (oppure
  `/data/avatars`): lì stanno avatar e allegati delle segnalazioni. La variabile
  `AVATAR_STORAGE_PATH` **non serve** se si usa il default `/data/avatars`; si imposta solo se il
  volume è montato altrove. — Rosario
- [x] `API_FOOTBALL_KEY` presente sul backend e quota giornaliera sufficiente per il periodo. —
  Rosario
- [ ] Notifiche push funzionanti sull'app Android (notifica di prova ricevuta). — Rosario
- [x] Nessun segreto nel repository: i soli ritrovamenti sono i falsi positivi in
  `.gitleaksignore`; il valore di `API_FOOTBALL_KEY=` in `infra/local/.env.example` è un testo
  segnaposto, non una chiave (verificato il 04/11/2026). Confermato da Rosario.

## 3. Email e contatto

- [x] Decisione del 04/11/2026: **il pilota parte senza email** (dominio Resend non verificato).
  Nessun tester riceve email; restano le notifiche in app e le push Android. Verificare la
  verifica dominio Resend prima di riattivare registrazione/recupero con email. — Rosario
- [x] La casella **info@globetrotta.it** riceve (confermato da Rosario il 04/11/2026): è il
  contatto dell'informativa per copia dati ed eliminazione.

## 4. Prova completa con un account Google nuovo

Da fare sia sul **web** sia nell'**app**:

- [ ] Accesso con Google; nel profilo risulta «Hai accettato l'informativa privacy». — Rosario
- [ ] Ingresso in una lega con un invito. — Rosario
- [ ] Mercato e formazione. — Rosario
- [ ] Partita con voti visibili. — Rosario
- [ ] «Segnala un problema» con una foto; la segnalazione compare nel pannello operatore. —
  Rosario
- [ ] Pannello operatore → «Torna all'app» esce correttamente (fix del 03/11). — Rosario
- [ ] Eliminazione account scrivendo `ELIMINA`. — Rosario

## 5. Dati e leghe

- [x] Voti dei turni calcolati (ricalcolo eseguito). — Rosario
- [ ] Leghe dei tester create, partecipanti invitati, calendario pronto. — Rosario
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

- [ ] Chi guarda i log di Railway (API e worker) e con che frequenza. — Rosario
- [ ] Canale per i tester: info@globetrotta.it; tempo di risposta dichiarato. — Rosario
- [ ] Piano se qualcosa si rompe: sospendere gli inviti, avvisare i tester, tornare al tag
  precedente (vedi `pilot_incident_runbooks.md`). — Rosario
- [ ] Controllo a 24 ore dal primo invito: errori nei log, segnalazioni arrivate, push consegnate.
  — Rosario

## Limiti noti da dire ai tester

- iPhone: solo sito web (niente app né notifiche push), iOS rimandato alla Fase 2.
- Possibili bug, interruzioni e, in casi eccezionali, perdita di dati (scritto nell'informativa).
