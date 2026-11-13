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

## Corse notturne (fino a 4 per notte, dalle 22 alle 5)
Le corse partono solo di notte (ora di Roma) per lasciare i token del mattino a Rosario. Un'unica attività le lancia alle **22:23, 00:23, 02:23 e 04:23**; ogni corsa capisce da sola quale è dall'ora di Roma in cui parte. La "notte" porta la data della sera in cui è iniziata (la corsa delle 00:23 appartiene alla notte iniziata il giorno prima).

| Corsa | Cosa copre |
|---|---|
| 22:23 | Mercato: aree 4 e 5 (scambi, aste sigillate e live, svincolati, esubero in attesa, crediti) |
| 00:23 | Primo gruppo a rotazione |
| 02:23 | Secondo gruppo a rotazione |
| 04:23 | Facoltativa: ripete i difetti trovati nella notte per escludere falsi positivi e controlla che i fixer abbiano consegnato `.patch` validi |

**Data del piano.** Dal 13/11/2026 le corse notturne anticipano il piano del giorno dopo: la data del piano è la data della notte **più un giorno** (il piano del 13/11 è stato eseguito nel pomeriggio di quel giorno). Per esempio la notte iniziata il 13/11 esegue il piano del 14/11, quella del 14/11 il piano del 15/11 (domenica: controllo a campione).

Rotazione dei gruppi (A = aree 1 e 2; B = aree 3 e 6; C = aree 7 e 8; D = aree 9, 10 e 11), in base al giorno dell'anno della data del piano (`tm_yday % 2`):
- pari → 00:23 gruppo A, 02:23 gruppo B
- dispari → 00:23 gruppo C, 02:23 gruppo D
- piano di domenica → controllo a campione: 00:23 aree 1-6, 02:23 aree 7-11, e verifica che le correzioni già pubblicate non si siano rotte.
Così ogni area è rivista ogni 2 notti.

Regole di consumo: se una corsa trova un limite d'uso o un errore di quota, si ferma e lo scrive nel rapporto; la corsa delle 04:23 si salta se una precedente ha incontrato limiti. Nessuna corsa parte fuori dalla fascia 22-5. Il rapporto indica corsa e gruppo eseguiti. I bug già in `known_issues.md` si rivalutano solo se l'area della corsa li riguarda.

## Scenario "turno vivo" (solo quando serve)
Se su dev c'è un turno con cutoff nelle prossime 24 ore, il coordinatore, oltre alla corsa normale, programma con `send_later` 2 o 3 controlli mirati (anche fuori dalla fascia notturna, sono brevi e mirati) (indicativamente a −2h, −10 minuti e +5 minuti dal cutoff). Ogni controllo riprende le leghe/formazioni create nella corsa del giorno e verifica: mosse tattiche e relativo conteggio a ridosso del blocco, blocco progressivo per partita, formazione automatica al primo blocco, cutoff e ricalcolo, notifiche di turno. Dove manca il dato sportivo scrive "non verificabile". Nei giorni senza turno vicino non si programma nulla. Ogni controllo finisce nel rapporto del giorno.

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
