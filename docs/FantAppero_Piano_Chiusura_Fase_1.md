# FantApperò — Piano operativo per chiudere la Fase 1

**Versione:** 1.0  
**Data audit:** 17 settembre 2026  
**Repository analizzato:** `app-appero/fantappero`  
**Commit analizzato:** `98fa151b4872269f0bd6d7b7648771c2e91aa662`  
**Obiettivo:** portare l'attuale piattaforma dalla condizione di Beta tecnicamente avanzata alla chiusura verificabile della Fase 1, senza aggiungere nuove funzionalità non indispensabili.

---

## 1. Conclusione dell'audit

FantApperò non è un prototipo vuoto. Il repository contiene una piattaforma reale e articolata con:

- backend FastAPI e PostgreSQL;
- migrazioni Alembic;
- autenticazione, verifica email, recupero password e sessioni;
- autorizzazioni globali e per lega;
- web app React;
- applicazione mobile Expo/React Native;
- gestione leghe, membri, inviti e fantallenatori;
- rose, crediti, asta, mercato, scambi e waiver;
- formazioni, lock, sostituzioni e risoluzione automatica;
- calendario H2H, turni, scoring, classifiche e omologazione;
- integrazione centralizzata con API-Football;
- processi asincroni con Redis e Celery;
- notifiche ed email;
- funzionalità AI;
- test unitari, di integrazione, di concorrenza ed E2E;
- strumenti di osservabilità, backup e disaster recovery.

Il problema non è quindi “costruire l'MVP da zero”. Il problema è **congelare il perimetro, verificare tutto ciò che è stato costruito, chiudere i gap rimasti, ottenere una vera parità web/mobile e provare il prodotto con utenti reali**.

La Fase 1 non può essere dichiarata conclusa soltanto perché il codice esiste o perché i test automatici passano. La chiusura richiede quattro risultati distinti:

1. **perimetro MVP completamente tracciato;**
2. **release candidate stabile e riproducibile;**
3. **pilot reale completato;**
4. **decisione finale GO/NO-GO registrata.**

---

## 2. Cosa significa “Fase 1 conclusa”

La Fase 1 è conclusa solamente quando sono vere contemporaneamente tutte queste condizioni:

- ogni requisito MVP ha uno stato certo e una prova;
- non esistono funzionalità dichiarate completate ma disponibili soltanto in demo;
- web e mobile offrono i medesimi flussi fondamentali;
- la build candidata è identificata da commit, tag, schema database e artefatti precisi;
- le integrazioni con API-Football sono state verificate con dati reali dei campionati scelti;
- un ambiente pilot separato è funzionante;
- backup e ripristino sono verificati sull'ambiente pilot;
- privacy, ruoli operativi e supporto sono stati approvati;
- almeno 3 leghe reali hanno usato il prodotto per almeno 28 giorni e 4 turni completi;
- gli eventuali problemi bloccanti emersi dal pilot sono stati risolti e ritestati;
- è stata registrata una decisione finale GO oppure NO-GO motivata.

### Tre traguardi da non confondere

| Traguardo | Significato |
|---|---|
| **Sviluppo Fase 1 completato** | Le funzionalità MVP previste sono implementate e testate. |
| **Beta pronta** | Esiste una release candidata distribuibile in un ambiente pilot sicuro e recuperabile. |
| **Fase 1 conclusa** | Il pilot reale è terminato, i KPI sono stati misurati e il gate finale è stato firmato. |

Esempio: una formazione può essere perfettamente implementata e coperta da test. Se però durante il pilot gli utenti mobile non riescono a salvarla prima del lock, lo sviluppo tecnico esiste ma la Fase 1 non è ancora chiusa.

---

## 3. Gestione delle funzionalità aggiunte fuori scope

Le funzionalità aggiunte fuori dal perimetro iniziale non devono essere eliminate automaticamente. Una volta integrate nel prodotto possono influenzare dati, permessi, navigazione e stabilità.

Per ciascuna funzione extra va scelta una delle seguenti destinazioni:

| Destinazione | Quando usarla |
|---|---|
| **INCLUSA_FASE1** | È già stabile, utile al pilot e non aumenta in modo rilevante il rischio. |
| **FEATURE_FLAG** | Il codice resta, ma la funzione non viene mostrata nel pilot finché non è verificata. |
| **SOLO_ADMIN** | Serve agli operatori ma non deve entrare nei flussi degli utenti pilota. |
| **FASE2** | Non è indispensabile alla validazione della Fase 1 e richiede ulteriore sviluppo. |
| **RIMOSSA_DALLA_RC** | È incompleta e compromette sicurezza o stabilità della release candidata. |

### Funzionalità extra già presenti da trattare con attenzione

- assistenti AI e formazione automatica delle squadre AI;
- profilo storico dei fantallenatori;
- directory e inviti nominativi;
- badge e notifiche degli inviti;
- live dettagliato delle partite;
- mercato evoluto, scambi, waiver e asta live;
- entitlement e billing;
- strumenti operator e pannelli amministrativi avanzati.

**Decisione consigliata:** mantenere queste funzioni nel codice, ma includere nel pilot soltanto quelle con parità web/mobile, test aggiornati e valore diretto per il flusso da validare. Le altre devono essere protette da feature flag o riservate agli operatori.

Esempio: se l'assistente AI funziona sul web ma non ha ancora un'esperienza mobile equivalente, non va cancellato; può essere disattivato nella release pilot e spostato nel backlog Fase 2.

---

## 4. Piano di chiusura

## Blocco A — Congelare il perimetro

### A1. Creare il registro completo dei requisiti

Occorre creare una matrice unica che colleghi ogni requisito e ogni card a:

- fonte documentale;
- priorità Must/Should;
- backend/API;
- web;
- mobile;
- migrazione database;
- test;
- evidenza manuale;
- stato;
- destinazione Fase 1/Fase 2;
- owner.

Stati ammessi:

- `IMPLEMENTED_VERIFIED`;
- `MVP_REMEDIATION`;
- `PHASE2_BACKLOG`;
- `SUPERSEDED`;
- `REJECTED`;
- `HUMAN_OPERATIONAL_GATE`;
- `EVIDENCE_TEMPLATE`.

Esempio di riga:

| Requisito | Backend | Web | Mobile | Test | Stato |
|---|---|---|---|---|---|
| Invito nominativo | Endpoint e servizio presenti | Directory + invio | Directory + invio | Integrazione + UI | `IMPLEMENTED_VERIFIED` |
| Risultati live | Endpoint fixture presenti | Lista e dettaglio | Da verificare su device | Test polling web | `MVP_REMEDIATION` |

### A2. Stabilire la gerarchia della documentazione

Il repository contiene documenti nati in momenti diversi. La precedenza consigliata è:

1. decisioni operative correnti in `docs/operations/` per pilot, sicurezza e deployment;
2. Documento Master, Requisiti Funzionali e Architettura Tecnica per perimetro MVP;
3. ADR e documenti API per decisioni tecniche;
4. Concept iniziale soltanto dove non è stato superato da decisioni successive;
5. wireframe e demo come rappresentazione UI, mai come fonte delle regole di dominio.

### A3. Aggiornare il README principale

Il `README.md` principale è vuoto. Deve diventare l'indice autorevole del progetto e includere:

- descrizione del prodotto;
- stato attuale;
- architettura;
- avvio locale;
- variabili d'ambiente;
- comandi di test;
- struttura della documentazione;
- distinzione demo/reale;
- limiti della release;
- riferimento al registro dei requisiti;
- percorso per contribuire senza introdurre nuovo scope.

**Criterio di completamento Blocco A:** il 100% delle 72 card M0.5–M5 e delle successive card Pre-M5.1/M5.1 è inventariato e nessuna riga è senza stato o owner.

---

## Blocco B — Chiudere i gap tecnici MVP

### B1. Verificare le card storicamente meno certificate

La documentazione segnala che M1 e M2 hanno commit meno granulari rispetto a M3 e M4. Vanno quindi verificati puntualmente almeno:

- pannello qualità dati sportivi;
- mosse tattiche;
- recupero della formazione precedente;
- bozze della formazione;
- rinvii e cambi dell'orario di una partita;
- lock individuale dopo variazione kickoff;
- rifiuto server-side di una formazione non più modificabile.

Esempio: una partita passa dalle 20:45 alle 18:30. Il sistema deve aggiornare il lock senza consentire a un utente di modificare alle 19:00 un calciatore già sceso in campo. Il controllo deve avvenire sul backend, non soltanto disabilitando un pulsante.

### B2. Completare il flusso risultati reale

La documentazione E2E precedente dichiara che il tab “Risultati” era statico e che il calcolo veniva attivato mediante seed/servizi interni. Sul commit candidato bisogna verificare:

- risultati accessibili realmente da web e mobile;
- aggiornamento del risultato H2H;
- distinzione fra Magic Points e Score;
- stato provvisorio, finale e omologato;
- dettaglio della composizione del punteggio;
- ricalcolo controllato dopo correzioni provider;
- impossibilità di modificare un turno omologato senza operazione auditata.

Esempio:

```text
Magic Points: Atletico Spritz 72,5 – 68,0 Real Mojito
Score H2H:    Atletico Spritz 2 – 1 Real Mojito
Stato:        Finale, non ancora omologato
```

Non devono apparire semplicemente `72,5 (2) – 68 (1)` senza spiegare la differenza.

### B3. Validare calendario H2H e turni europei

Verificare su leghe da 4, 5, 8 e 10 partecipanti:

- cicli completi;
- nessun incontro duplicato nello stesso ciclo;
- bye corretto con numero dispari;
- alternanza casa/trasferta;
- mapping esplicito tra giornata H2H e finestra europea;
- comportamento con fixture spostate, sospese o cancellate;
- rigenerazione idempotente;
- conservazione delle giornate già iniziate.

Esempio: con 5 partecipanti un ciclo richiede 5 giornate e in ogni giornata una squadra riposa. Al termine del ciclo ciascuna squadra deve avere esattamente un turno di riposo.

### B4. Validare i dati reali di API-Football

Il client provider è ben strutturato, ma prima del pilot devono essere chiuse o accettate formalmente le open question sui dati critici:

- ruolo unico del calciatore nel listone;
- identificazione affidabile di trasferimenti e uscita dai campionati;
- rigori parati e sbagliati;
- autogol;
- doppia ammonizione/espulsione;
- minuti giocati;
- partite rinviate;
- disponibilità per infortunio o squalifica;
- correzioni tardive del provider;
- copertura reale dei cinque campionati.

Per ogni dato critico servono:

1. endpoint sorgente;
2. regola di normalizzazione;
3. fallback;
4. test con payload reale redatto;
5. decisione sul comportamento quando il dato manca.

Esempio: se il provider non rende distinguibile un rigore parato da un rigore calciato fuori, il sistema non deve assegnare automaticamente `+3`. Deve mettere il caso in coda operatore oppure applicare un fallback esplicitamente approvato.

### B5. Completare i test di concorrenza rimasti

La copertura è già ampia, ma risultano da decidere o completare test specifici per:

- risoluzione waiver concorrente;
- approvazione amministrativa di uno scambio concorrente;
- ricalcolo e omologazione contemporanei;
- aggiornamento kickoff mentre una formazione viene salvata.

Esempio: due squadre provano ad acquisire contemporaneamente lo stesso giocatore. Il risultato accettabile è una sola assegnazione, un solo movimento di credito e nessun saldo negativo.

**Criterio di completamento Blocco B:** nessun requisito Must rimane `MVP_REMEDIATION`; ogni eccezione è spostata esplicitamente in Fase 2 oppure accettata come rischio firmato.

---

## Blocco C — Parità web/mobile reale

La presenza di schermate mobile non dimostra automaticamente la parità funzionale.

### C1. Creare una matrice di parità

Verificare per ogni flusso:

- endpoint utilizzato;
- campi mostrati;
- azioni disponibili;
- permessi;
- stati loading, empty, error, success e forbidden;
- messaggi;
- deep link;
- accessibilità;
- test automatici;
- prova su dispositivo reale.

Flussi minimi:

1. registrazione e verifica email;
2. login, refresh e logout;
3. recupero password;
4. creazione lega;
5. ingresso con codice;
6. invito nominativo;
7. accettazione/rifiuto invito;
8. selezione della lega attiva;
9. rosa e crediti;
10. asta/mercato previsto dal pilot;
11. formazione e lock;
12. turni europei;
13. matchup H2H;
14. risultati e classifica;
15. notifiche;
16. profilo e privacy;
17. funzioni amministrative indispensabili.

### C2. Introdurre E2E mobile su dispositivo/emulatore

I test componenti non bastano. Serve almeno un flusso mobile automatizzato o riproducibile su emulator/device farm:

```text
registrazione → verifica email → login → ingresso/creazione lega
→ rosa pronta → salvataggio formazione → visualizzazione risultato
→ operazione di mercato → logout/login con sessione conservata
```

Esempio di difetto che i test web non trovano: il refresh token funziona nel `localStorage` del browser, ma la sessione mobile viene persa dopo la chiusura completa dell'app.

### C3. Eliminare le ambiguità demo/reale

- La modalità `?persona=` deve restare esclusivamente DEV.
- Nessun pulsante della release pilot deve mostrare successo senza una risposta reale del backend.
- Le schermate demo devono essere escluse o chiaramente separate nella build pilot.
- I deep link devono rispettare autorizzazioni reali server-side.

**Criterio di completamento Blocco C:** tutti i flussi MVP sono equivalenti su web e mobile oppure hanno una motivazione `N/A mobile` approvata perché non generano alcuna esperienza utente o amministrativa.

---

## Blocco D — Release candidate e qualità

### D1. Congelare la release candidate

Creare un manifest contenente:

- commit Git completo;
- tag versione;
- branch;
- revisione Alembic;
- digest immagini Docker;
- build web;
- versione app mobile;
- versione contratti condivisi;
- configurazione feature flag;
- ambiente target;
- data del freeze;
- elenco delle evidenze ancora valide e di quelle da rigenerare.

Esempio:

```yaml
release: fase1-rc1
commit: <sha completo>
database_revision: <alembic head>
web_artifact: <digest>
mobile_android: <version/build>
mobile_ios: <version/build>
pilot_environment: staging-pilot-eu
```

### D2. Rendere bloccanti i gate essenziali

Sulla release candidate devono essere obbligatori:

- lint e formattazione;
- type-check;
- test backend;
- test frontend;
- build packages;
- build web;
- build mobile;
- migrazioni su database vuoto;
- migrazione di un database popolato;
- E2E critico web;
- E2E critico mobile;
- secret scan;
- security scan con soglie approvate.

L'E2E critico non dovrebbe restare soltanto informativo: se fallisce, la release non deve essere candidata al pilot salvo accettazione esplicita del rischio.

### D3. Rieseguire performance e capacità

Le prove di agosto appartengono a una versione precedente. Dopo le aggiunte fuori scope vanno rieseguite almeno:

- smoke;
- steady load;
- spike;
- recovery;
- benchmark worker;
- scenario live;
- scenario mobile con polling.

I budget devono essere ratificati, non soltanto proposti.

Esempio di budget da approvare:

```text
API critiche: p95 < 800 ms
Errori HTTP sotto carico: < 1%
Salvataggio formazione al picco: p95 < 1.500 ms
Aggiornamento live visibile: entro 60 secondi dal dato normalizzato
```

I valori definitivi devono essere scelti dal team sulla base dell'ambiente reale.

### D4. Rivalidare la sicurezza

Prima del pilot:

- aggiornare audit Python e JavaScript;
- rivalutare Starlette, Playwright, Expo e dipendenze transitive note;
- rieseguire secret scan sulla storia e sul commit candidato;
- verificare header HTTP e configurazione CORS nel deployment reale;
- verificare rate limiting dietro il reverse proxy reale;
- testare IDOR e accessi cross-league;
- verificare upload avatar;
- controllare cancellazione ed export privacy;
- verificare che demo e pannelli operator non siano esposti impropriamente.

**Criterio di completamento Blocco D:** una release candidata riproducibile supera tutti i gate bloccanti e non presenta finding Critical/High aperti non formalmente accettati.

---

## Blocco E — Ambiente pilot e operatività

### E1. Preparare un ambiente pilot separato

Deve esistere un ambiente diverso da sviluppo e test, con:

- dominio e TLS;
- PostgreSQL persistente;
- Redis;
- API;
- worker e scheduler;
- web app;
- distribuzione mobile controllata;
- segreti esterni al repository;
- storage avatar persistente;
- logging centralizzato;
- alert;
- provider API-Football configurato;
- email transazionali reali;
- feature flag congelate.

### E2. Backup off-site e disaster recovery

Il backup non deve risiedere sullo stesso disco del database.

Servono:

- backup automatico almeno giornaliero;
- cifratura;
- copia off-site;
- retention approvata;
- monitoraggio del job;
- alert in caso di fallimento;
- prova di restore su ambiente isolato;
- procedura di cutover;
- owner principale e sostituto.

Obiettivi documentati da confermare:

- RPO massimo: 24 ore;
- RTO massimo: 2 ore;
- restore tecnico del dataset Beta: massimo 30 minuti.

Esempio: non basta vedere il file `.dump`. Bisogna ripristinarlo su un PostgreSQL vuoto, eseguire le verifiche applicative, confrontare utenti/leghe/rose/formazioni e misurare il tempo impiegato.

### E3. Osservabilità reale

L'attuale endpoint `/metrics` è process-local. Nel deployment con più worker serve una raccolta aggregata oppure bisogna dichiarare quali altre fonti costituiscono la verità operativa.

Monitorare almeno:

- disponibilità API;
- tasso 5xx;
- latenza;
- code Celery;
- job falliti;
- ritardo sincronizzazione provider;
- errori di normalizzazione;
- backup;
- spazio database;
- invio email;
- crash web/mobile.

**Criterio di completamento Blocco E:** l'ambiente pilot può essere ripristinato, monitorato e supportato senza dipendere dal computer di sviluppo.

---

## Blocco F — Governance, privacy e supporto

### F1. Assegnare ruoli reali

Prima di invitare utenti devono essere nominati:

- decision owner;
- pilot coordinator;
- incident coordinator e sostituto;
- platform owner e sostituto;
- security owner;
- privacy contact;
- amministratore per ciascuna lega pilota.

### F2. Approvare privacy e trattamento dati

Occorre predisporre e approvare:

- informativa del pilot;
- termini della Beta;
- dati raccolti;
- finalità;
- retention;
- modalità di ritiro;
- esportazione e cancellazione account;
- trattamento dei ticket;
- divieto di inserire password/token nei ticket;
- gestione di eventuali minori, preferibilmente esclusi dal primo pilot.

### F3. Attivare un vero processo di supporto

Definire:

- canale utenti;
- canale urgente interno;
- sistema ticket;
- orari;
- priorità P0/P1/P2/P3;
- tempi di presa in carico;
- escalation;
- comunicazione incidenti;
- chiusura e post-mortem.

Esempio:

```text
P0: piattaforma inutilizzabile durante il lock/formazione.
P1: una lega non può calcolare o omologare il turno.
P2: una funzione secondaria non è disponibile ma esiste workaround.
P3: problema grafico o richiesta migliorativa.
```

**Criterio di completamento Blocco F:** ruoli, privacy, canali e soglie sono approvati da persone reali e non lasciati come placeholder nella documentazione.

---

## Blocco G — Pilot reale

### G1. Selezione della coorte

Configurazione consigliata dalla documentazione esistente:

- 3–5 leghe;
- 6–12 partecipanti per lega;
- almeno un admin disponibile per lega;
- utenti non composti soltanto dal team di sviluppo;
- nessun premio economico o obbligo dipendente dall'esito;
- almeno 28 giorni;
- almeno 4 turni completi per lega.

### G2. Smoke prima dell'avvio

Ogni lega deve completare almeno:

```text
registrazione → verifica email → login → lega → rosa
→ formazione → risultato → mercato → notifica
```

Lo smoke va ripetuto su web e mobile.

### G3. KPI da raccogliere

KPI minimi:

- leghe attive;
- partecipanti attivi;
- durata del pilot;
- turni completati;
- completamento del flusso critico;
- blocchi aperti;
- rispetto dei tempi di supporto;
- incidenti P0/P1;
- esito delle prove di capacità;
- finding di sicurezza;
- continuità dei backup;
- usabilità percepita;
- intenzione degli admin di continuare a usare il prodotto.

Soglie proposte già presenti nella documentazione:

- almeno 90% di completamento complessivo del flusso critico;
- almeno 80% per ogni lega;
- zero blocker aperti al gate;
- zero incidenti P0;
- zero P1 non risolti o non accettati;
- valutazione media di usabilità almeno 4/5;
- almeno 80% degli admin intenzionati a continuare.

Queste soglie devono essere approvate prima dell'avvio, non modificate dopo aver visto i risultati.

### G4. Decisione finale

Alla fine del pilot:

- **GO:** tutte le soglie obbligatorie sono rispettate;
- **GO CON REMEDIATION:** ammesso soltanto se le remediation non riguardano sicurezza, perdita dati o flussi essenziali e hanno owner/data;
- **NO-GO:** una o più condizioni critiche non sono soddisfatte.

La decisione deve contenere:

- release esaminata;
- periodo;
- leghe partecipanti in forma pseudonimizzata;
- KPI;
- incidenti;
- rischi residui;
- firme/approvazioni;
- backlog Fase 2.

**Criterio di completamento Blocco G:** il pilot è realmente eseguito e il documento GO/NO-GO è approvato. Un dry-run interno non sostituisce questo passaggio.

---

## 5. Ordine consigliato di esecuzione

| Ordine | Attività | Tipo | Stima indicativa |
|---:|---|---|---:|
| 1 | Freeze temporaneo delle nuove feature | Decisione | 0,5 giorni |
| 2 | Registro completo requisiti e funzioni extra | Analisi | 2–4 giorni |
| 3 | Decisione Fase 1/feature flag/Fase 2 | Product | 1–2 giorni |
| 4 | Chiusura gap MVP rilevati | Sviluppo | Da stimare dopo registro |
| 5 | Matrice e remediation web/mobile | Sviluppo/QA | 3–8+ giorni |
| 6 | E2E web e mobile completi | QA | 2–5 giorni |
| 7 | Freeze release candidate | Release | 1–2 giorni |
| 8 | Performance e sicurezza sulla candidata | QA/Security | 2–5 giorni |
| 9 | Ambiente pilot, backup e osservabilità | Operations | 2–5+ giorni |
| 10 | Privacy, ruoli e supporto | Governance | 2–5+ giorni |
| 11 | Onboarding e smoke della coorte | Pilot | 2–5 giorni |
| 12 | Pilot reale | Pilot | minimo 28 giorni/4 turni |
| 13 | Remediation finale e retest | Sviluppo/QA | dipende dagli esiti |
| 14 | Gate GO/NO-GO | Decisione | 1–3 giorni |
| 15 | Backlog definitivo Fase 2 | Product | 2–5 giorni |

Le stime non vanno sommate meccanicamente: alcune attività possono procedere in parallelo, mentre il pilot richiede inevitabilmente tempo reale.

---

## 6. Priorità immediata: cosa fare adesso

### P0 — Da fare prima di altro sviluppo

1. Bloccare nuove feature.
2. Scegliere formalmente il commit/branch candidato.
3. Creare il registro completo dei requisiti.
4. Classificare tutte le funzioni extra.
5. Verificare gap tra backend, web e mobile.
6. Decidere cosa entra nella build pilot e cosa viene disattivato.

### P1 — Da fare prima del pilot

1. Chiudere tutti i Must `MVP_REMEDIATION`.
2. Completare E2E reale web e mobile.
3. Validare API-Football con dati reali.
4. Rieseguire performance e security review.
5. Congelare RC e manifest.
6. Preparare ambiente pilot e backup off-site.
7. Assegnare owner, privacy contact e supporto.

### P2 — Da fare durante e dopo il pilot

1. Raccogliere KPI.
2. Gestire incidenti.
3. Correggere i blocker.
4. Rieseguire i test sulla stessa RC o su una RC successiva tracciata.
5. Registrare il gate finale.
6. Congelare il backlog Fase 2.

---

## 7. Cose da non fare in questa fase

- Non aggiungere altre funzionalità solo perché interessanti.
- Non riscrivere l'architettura in microservizi senza una necessità misurata.
- Non cambiare contemporaneamente provider sportivo e regole di scoring.
- Non considerare una schermata presente come prova che il flusso funzioni.
- Non considerare un test demo come prova di autorizzazione reale.
- Non dichiarare parità mobile basandosi sul solo numero di schermate.
- Non usare seed sintetici come unica validazione dei risultati reali.
- Non iniziare il pilot senza backup, ruoli e privacy approvati.
- Non spostare le soglie KPI dopo aver osservato i risultati.
- Non chiamare “Fase 1 conclusa” una Beta che non è stata usata da leghe reali.

---

## 8. Definition of Done finale

La Fase 1 di FantApperò è conclusa quando:

- [ ] il perimetro è congelato;
- [ ] tutte le fonti documentali sono inventariate;
- [ ] tutte le card hanno stato, owner e prova;
- [ ] le funzionalità extra hanno una destinazione esplicita;
- [ ] tutti i Must MVP sono implementati e verificati;
- [ ] web e mobile sono funzionalmente equivalenti nei flussi MVP;
- [ ] gli E2E critici web e mobile sono bloccanti e verdi;
- [ ] API-Football è verificata sui campionati e dati necessari;
- [ ] la release candidate è riproducibile;
- [ ] performance e sicurezza sono rivalidate sulla candidata;
- [ ] l'ambiente pilot è separato e osservabile;
- [ ] backup off-site e restore sono provati;
- [ ] ruoli, privacy e supporto sono approvati;
- [ ] almeno 3 leghe reali completano 28 giorni e 4 turni;
- [ ] KPI e incidenti sono raccolti con fonti verificabili;
- [ ] non restano blocker critici aperti;
- [ ] la decisione GO/NO-GO è registrata;
- [ ] il backlog Fase 2 è separato e prioritizzato.

---

## 9. Valutazione finale

FantApperò è già oltre un MVP embrionale: possiede molte funzioni che normalmente arriverebbero dopo una prima Beta. Questo è contemporaneamente un vantaggio e un rischio.

Il vantaggio è che gran parte del prodotto esiste già. Il rischio è continuare ad aggiungere funzionalità mentre rimangono non certificati il perimetro, la parità mobile, il comportamento con dati provider reali e l'operatività del pilot.

La strada più breve per arrivare alla fine della Fase 1 non è sviluppare ancora. È:

> **fermare lo scope → inventariare → verificare → correggere → congelare → pilotare → decidere.**

Solo dopo il gate finale conviene aprire formalmente la Fase 2.
