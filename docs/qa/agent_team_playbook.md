# Squadra di agenti QA su dev: regole e piano di test

Questo file è il manuale che ogni esecuzione programmata legge all'inizio. Vale **solo per l'ambiente dev**.

## Regole non negoziabili
1. **Solo dev.** Sito `https://dev.fantappero.it`, API `https://fantappero-api-dev.up.railway.app`. Mai `pilota.fantappero.it` né le sue API, nemmeno in sola lettura.
2. **Nessuna funzione nuova.** Si testa e si correggono bug. Idee e miglioramenti vanno in una sezione a parte del rapporto ("Suggerimenti"), mai implementati.
3. **Niente push, niente rami nuovi, niente modifiche a `main` o `pilota`.** Il fixer lavora in locale, verifica, e mette la patch (diff) nel rapporto. Applica e pusha solo Rosario, in una sessione interattiva, dopo averla approvata.
4. **Tutto viene riportato a Rosario prima di agire.** Il rapporto finale è l'unico output che conta.
5. **Solo account di test** `qa-01 … qa-08@test.fantappero.it` e leghe con nome `QA-<data>-<corsa>-<lettera>`. Mai toccare dati di altri utenti.
6. **Non indovinare né usare credenziali altrui.** Dev ha la registrazione senza verifica email e la modalità test spenta: gli account si creano da soli.
7. **Gentilezza con il server:** una richiesta alla volta per account, pause su 429, nessun ciclo stretto. Il login ha un rallentamento crescente per account: non sbagliare password apposta più di una volta.
8. Segreti e token mai nei rapporti.

## Ruoli (dentro ogni esecuzione)
- **Coordinatore** (la sessione principale): prepara account e leghe, assegna le aree ai tester, deduplica con `docs/qa/known_issues.md`, assegna ai fixer solo i bug confermati e riproducibili, scrive il rapporto.
- **Tester** (un agente per area): eseguono le checklist qui sotto, per ogni problema registrano: passi, atteso, ottenuto, richiesta e risposta HTTP (senza segreti), gravità (bloccante / alta / media / bassa), area.
- **Fixer** (uno per bug confermato, solo se il bug è nel codice): trova la causa, scrive la correzione minima con test, la prova in locale (Postgres/Redis locali, vedi `docs/development/local_environment.md`) e consegna al coordinatore causa + diff + test eseguiti. Non applica nulla.
  - **Ogni fixer lavora in una copia sua**, mai nella cartella condivisa: `git worktree add /tmp/fix-<id> HEAD` (o `git clone` locale) e un database di test con nome proprio (`fantappero_fix_<id>_test`, il nome deve finire con `_test`). Vietato `git stash`, `git checkout` o `git reset` nella cartella condivisa: si pestano i piedi a vicenda e i test diventano inaffidabili.
  - Il confronto "prima/dopo" si fa con due worktree (uno senza la correzione, uno con), non con lo stash.
  - Mai due `pytest` sullo stesso database nello stesso momento.
  - Il diff consegnato deve essere un file `.patch` applicabile con `git apply` sul ramo `main`.

## Rotazione delle aree (una esecuzione al giorno)
Per contenere il consumo, ogni esecuzione copre le aree **4 e 5 (mercato) sempre**, più **due gruppi a rotazione** secondo il giorno dell'anno (`oggi.timetuple().tm_yday % 4`):
- `0` → aree 1 e 2 (accesso/profilo, leghe/inviti)
- `1` → aree 3 e 6 (rosa/crediti, formazione)
- `2` → aree 7 e 8 (turni/calendario/classifica, notifiche)
- `3` → aree 9, 10 e 11 (web, coerenza web/mobile, salute)
Così ogni area non di mercato viene riesaminata ogni 4 giorni. Il rapporto indica quale rotazione è stata eseguita. I bug già in `known_issues.md` si rivalutano solo se l'area del giorno li riguarda.
Una volta alla settimana (di domenica) il coordinatore fa un controllo a campione su tutte le aree e verifica che le correzioni già pubblicate non si siano rotte.

## Scenario "turno vivo" (solo quando serve)
Se su dev c'è un turno con cutoff nelle prossime 24 ore, il coordinatore, oltre alla corsa normale, programma con `send_later` 2 o 3 controlli mirati (indicativamente a −2h, −10 minuti e +5 minuti dal cutoff). Ogni controllo riprende le leghe/formazioni create nella corsa del giorno e verifica: mosse tattiche e relativo conteggio a ridosso del blocco, blocco progressivo per partita, formazione automatica al primo blocco, cutoff e ricalcolo, notifiche di turno. Dove manca il dato sportivo scrive "non verificabile". Nei giorni senza turno vicino non si programma nulla. Ogni controllo finisce nel rapporto del giorno.

## Preparazione di ogni esecuzione
1. Accedi con gli otto account `qa-01..08@test.fantappero.it`, password fissa `QaAgenti!2026x`. Se il login fallisce con credenziali errate, registra l'account (`POST /auth/register`) e riprova. Se risponde `tester_only`, fermati e segnala: la modalità test è stata riaccesa.
2. Crea le leghe necessarie alle aree del giorno (se la rotazione non tocca turni/calendario, la lega B non serve) (le intestazioni dei percorsi sono nei router `backend/src/*/router.py` e nei client `apps/web/src/api/`):
   - **QA-…-A (mercato)**: 6 partecipanti (qa-01 proprietario, qa-02..06 con invito o codice), regole standard.
   - **QA-…-B (ciclo di vita)**: 4 partecipanti (minimo consentito), usata per attivazione, calendario e turni.
3. Alla fine prova a eliminare le due leghe; se non è possibile lasciale, il nome le rende riconoscibili.

## Aree e checklist (ogni voce: esito ok / difetto)
### 1. Accesso, profilo, privacy
Registrazione (campi, password debole, email duplicata, risposta generica), login, logout, sessione scaduta/refresh, profilo (nome, nickname univoco senza maiuscole, avatar), preferenze notifiche per evento e canale, quiet hours, esportazione dati, eliminazione account, informativa privacy. Rate limit registrazione/login coerenti.

### 2. Leghe, inviti, partecipanti
Creazione lega (nome, stagione, competizioni, preset standard e regole), codice invito e adesione, invito nominale (accetta, rifiuta, revoca, scadenza, duplicati), elenco partecipanti, directory fantallenatori, ruoli (proprietario/membro), sostituzione partecipante, uscita, eliminazione lega, permessi: un membro non deve poter fare azioni da proprietario (verifica ogni endpoint admin con un account membro: deve rispondere negato).

### 3. Rosa, listone, crediti
Listone (conteggi per ruolo, ricerca, filtro ruolo, ruoli effettivi e override), assegnazione manuale di uno slot (limiti per ruolo 3/11/11/10, calciatore già in un'altra rosa, crediti insufficienti), svincolo con rimborso, import CSV (anteprima e applicazione, errori), riempimento casuale/AI, movimenti crediti coerenti con il saldo (saldo ricostruito = saldo), storico rosa, esubero in attesa visibile e riparato dopo uno svincolo.

### 4. Mercato: scambi
Proposta (offri/chiedi, solo giocatori, solo crediti, scadenza facoltativa, destinatario, limite proposte attive), accetta, rifiuta, annulla, controproposta (la vecchia diventa "superata", la nuova è visibile al destinatario), scadenza, approvazione dell'amministratore se richiesta, doppia accettazione concorrente (una sola vince), crediti e rosa aggiornati subito su entrambi i lati, scambio sbilanciato con rosa piena (slot extra, giocatore bloccato), esubero di ruolo, riconciliazione dopo svincolo o altro scambio, notifiche (titolo, link che apre lo scambio giusto), filtri Ricevute/Inviate/In corso/Tutte coerenti con gli stati, statistiche "Da gestire / Inviate in corso / Scambi conclusi", scambi chiusi a turno in corso.

### 5. Mercato: aste e svincolati
Asta a buste: sessione (finestra, una sola attiva), offerta (importo, saldo, ritiro, rosa piena o ruolo pieno ammessi), chiusura, risoluzione (vincitore, spareggio con sessione figlia, idempotenza, crediti addebitati una volta), esiti visibili. Asta live: tutte le modalità di chiamata, rilanci, timer, passaggio, aggiudicazione, scambio immediato a rosa piena. Svincolati (waiver): offerta con calciatore da svincolare, risoluzione. Interruttore apri/chiudi mercato (effetto su asta e scambi, scambi sempre disponibili).

### 6. Formazione
Moduli approvati, selezione titolari e panchina, ordine panchina, calciatori bloccati/indisponibili/fuori rosa (visibili ma non selezionabili), blocco progressivo per partita, mosse tattiche (massimo e conteggio), bozza e salvataggio, copia formazione precedente, formazione automatica al primo blocco, validazioni server (ruolo, duplicati, non in rosa), formazioni degli altri partecipanti leggibili (scelta di Rosario, non è un difetto: non segnalarlo), operatore.

### 7. Turni, calendario, classifica
Generazione calendario (partecipanti pari/dispari, giornate, scontri diretti), attivazione lega (blocchi: rose complete, crediti), turni e finestre europee, cutoff e ricalcolo, partite del turno e orari, risultati e voti (se i dati sportivi di dev li hanno), classifica e fantapunti, scontro diretto, omologazione e correzioni, notifiche di turno. Dove mancano dati sportivi (nessuna partita giocata) registra "non verificabile" invece di inventare.

### 8. Notifiche
Centro notifiche (elenco, segna letta, badge), generate da: invito, scambio (tutti gli stati), asta, turno, formazione in scadenza. Link profondo corretto verso la schermata giusta, preferenze rispettate, nessun duplicato.

### 9. Web (browser headless, Playwright è già installato)
Viewport desktop 1280 e mobile 390: ogni pagina principale carica senza errori in console né richieste fallite, nessun scorrimento orizzontale, tab Mercato (Rosa/Asta/Scambi), controproposta e rifiuto che chiude il pannello, selettore calciatori dell'asta, contrasto leggibile in tema chiaro e scuro.

### 10. Coerenza web/mobile (letture)
Confronta stessi dati letti dall'API con quello che mostrano le etichette del web: stati scambi, conteggi, colori ruolo (P verde, D giallo, C blu, A rosa/rosso). L'app mobile non si apre: segnala solo discrepanze di contratto/etichette trovate nel codice (`apps/mobile`).

### 11. Salute e prestazioni
`/live`, `/ready`, tempi di risposta delle letture principali (segnala oltre 2 secondi), errori 5xx in qualunque richiesta (sempre difetto), risposte che espongono dati altrui.

## Gravità
- **Bloccante**: impedisce un flusso principale o perde/duplica crediti o giocatori.
- **Alta**: risultato sbagliato ma aggirabile; permessi aggirabili.
- **Media**: etichette/conteggi incoerenti, errori non bloccanti.
- **Bassa**: estetica, testi.

## Formato del rapporto finale (in italiano, breve in cima)
1. **Riepilogo in 5 righe**: cosa è stato provato, esito, numero di problemi nuovi per gravità, cosa richiede una decisione.
2. **Problemi nuovi** (uno per voce): titolo, gravità, area, passi per riprodurre, atteso/ottenuto, prove (richiesta/risposta), causa probabile, patch proposta del fixer (diff + test) o "non nel codice / da indagare".
3. **Problemi già noti ancora presenti** (elenco, senza ripetere i dettagli).
4. **Non verificabile** e perché.
5. **Suggerimenti** (mai implementati).
6. **Ordini del coordinatore** per la prossima esecuzione (cosa approfondire).

## Durata
30 giorni, due esecuzioni al giorno (07:23 e 19:23, ora italiana). Alla scadenza (`2026-12-12`) l'attività si disattiva da sola.
