# FantApperò — Fase 2: idee e domande aperte

Ramo `fase-2`, creato il 24/11/2026 su richiesta di Rosario, partendo da `main`. Il ramo **non va su nessun sito**: dev e pilota restano legati a `main`, così le correzioni della fase pilota continuano come prima. Quando servirà provare codice della Fase 2 si valuterà un terzo ambiente Railway («fase2», con database proprio), solo con il via di Rosario.

**Quando:** apertura prevista a inizio gennaio 2027, dopo la chiusura del pilota e il gate finale del piano di chiusura Fase 1 (`docs/FantAppero_Piano_Chiusura_Fase_1.md`).

**Primo lavoro all'apertura:** rivedere la documentazione e trasformare questa raccolta nel backlog ordinato della Fase 2 (scheda EP13-12), facendo prima a Rosario le domande aperte in fondo.

## 1. Rimandati alla Fase 2 durante la chiusura della Fase 1
1. **Club e formazione personale prima della lega** (EP13-F01, discovery): un utente ha un suo club e una sua formazione anche senza essere in una lega. Solo idea da esplorare.
2. **App per iPhone (iOS):** oggi solo APK Android, l'iPhone usa il sito. Serve l'account Apple Developer, la pubblicazione e le notifiche push.
3. **Voto FantApperò con un modello addestrato** (OQ-08/OQ-09): invece di pesi scelti a mano per ruolo, un modello addestrato sui dati storici. Lavoro di analisi dati.
4. **Cambio di stagione** (OQ-15): verificare dal vivo (agosto/settembre) identificativi, calendario e listone quando il fornitore passa alla stagione nuova.
5. **Backup e ripristino del database:** oggi non c'è un backup automatico vero; serve un piano Railway a pagamento e una prova di ripristino.
6. **Registri centralizzati e allarmi:** oggi i problemi si vedono solo guardando a mano i registri di Railway.
7. **Assistenti AI** (viceallenatore, confronto, obiettivi, analista): basi già nel codice (`apps/web/src/api/aiAssistant.ts`), senza schermate.
8. **Abbonamento «Pro» e pagamenti:** basi nel codice (`apps/web/src/api/billing.ts`: permessi, esportazioni Pro), senza schermate né pagamenti; va deciso cosa è gratis e cosa a pagamento.
9. **Elenco completo della Fase 2** (EP13-12, mai fatta): un unico backlog ordinato da tutte le fonti.

## 2. Nate durante il pilota (23-24/11/2026)
10. **Chiavi del fornitore separate** per dev e pilota: oggi condividono la stessa quota giornaliera (il 23/11 è finita e ha ritardato l'omologazione di 2 ore).
11. **Terzo ambiente Railway «fase2»** con database proprio, aggiornato dal ramo `fase-2`.

## 3. Idee di Rosario (24/11/2026)
12. **Operatore «visitatore» in qualsiasi lega:** tasto «Entra nella lega» nel pannello operatore; l'operatore usa la lega con piene funzionalità anche se non è sua (oggi esiste solo l'impersonazione di un utente preciso).
13. **Sezione «Master»:** un campionato e un gioco a parte rispetto alle leghe normali, magari a pagamento (collegata ai punti 1 e 8).
14. **Richiesta di ingresso:** un fantallenatore sceglie una lega e chiede di entrarci; l'admin accetta o rifiuta (oggi può solo invitare l'admin).
15. **Classifiche generali del gioco:** una per le leghe Master e una per le leghe normali, sui fantapunti di tutte le giornate, con un premio finale per tenere tutti in gioco fino all'ultima giornata.

## 3-bis. Idee di Rosario (27/11/2026)
16. **La Redazione: giornale di lega e della Master.** Una «redazione» che ogni giorno racconta ai fantallenatori ciò che succede nella loro lega, come i titoli della Gazzetta: scontri, mercato (scambi, aste, svincoli), classifica, turni saltati, record. Ogni lega ha il suo «Giornale» e una notifica al giorno; la lega Master (idea 13) ha una prima pagina con le notizie di tutte le leghe in ordine di importanza. In teoria la redazione potrebbe anche dare i voti (collegata all'idea 3: i voti si calcolano da numeri, il modello scrive solo i commenti).
    - **Basi già nel codice:** assistenti AI (`backend/src/ai_assistant/`, oggi senza modello esterno: la scrittura del testo è un punto sostituibile, `generation.py`), notifiche con invio push ed email, orari di silenzio e codice anti-duplicato.
    - **Come:** 1) giornale con titoli a modello, senza AI (fatti dal database, punteggio di «notiziabilità», frasi pronte in italiano, pagina «Il Giornale» e una notifica al giorno); 2) testi scritti da un modello a partire dai soli fatti, con controllo automatico di nomi e numeri e ripiego sul titolo a modello; 3) prima pagina della Master con priorità; 4) voti calcolati da numeri, il modello li commenta soltanto.
    - **Costi (stima del 27/11, da ricontrollare prima di decidere):** con 6.000 token di fatti in ingresso e 1.500 di testo in uscita per edizione, 100 leghe al giorno (3.000 edizioni al mese) costano circa 4 $ con Haiku 5.5, 80 $ con Sonnet 5.5 e 160 $ con Opus 5.5; la metà con la generazione a blocchi di notte («batch»); 10 volte tanto con 1.000 leghe. La spesa vera è lo sviluppo: a occhio il passo 1 vale circa un lavoro e mezzo come il sostituto, il passo 2 mezzo lavoro, il passo 3 uno.
    - **Rischi:** testi che inventano fatti (si riduce passando solo fatti e controllando nomi e numeri), battute sui partecipanti per nome, costi che crescono con le leghe (tetto giornaliero per lega), chiave del modello separata per dev e pilota (come l'idea 10).
17. **Coppe nella carriera del calciatore** (rimandata il 28/11 da Rosario: «al momento non mi interessano»). Deciso il 22/11: media e Valore contano solo il campionato, ma Champions, coppe nazionali e supercoppe devono comparire nella tabella «Carriera» della scheda. Oggi la carriera ha solo righe di campionato anche per chi gioca le coppe, perché l'import chiede al fornitore `/players?league=<campionato>` (`backend/src/sports_data/season_stats/provider_import.py`). Per averle servono più chiamate al fornitore, quindi più quota.

## 4. Domande da fare a Rosario all'apertura della Fase 2
- **Punto 12:** «piene funzionalità» vuol dire che l'operatore può anche cambiare cose (regolamento, formazioni, mercato) o solo vedere tutto? I membri della lega devono vedere che l'operatore è entrato (registro, avviso)?
- **Punto 13:** come si entra nella Master (iscrizione libera, a pagamento, su invito)? Regole diverse dalle leghe normali?
- **Punto 14:** le leghe devono poter essere «aperte alle richieste» con un'opzione dell'admin, così non tutte compaiono in elenco? Cosa vede chi cerca una lega (nome, campionati, posti liberi, regolamento)?
- **Punto 15:** classifica dei **fantallenatori** (vince il singolo con più fantapunti fra tutte le leghe) o delle **leghe** (vince la lega con più punti sommando i suoi fantallenatori)? Nel secondo caso le leghe con più squadre partono avvantaggiate: meglio la media per squadra. Che premio, e chi lo assegna?
- **Punto 8:** cosa resta gratis e cosa diventa «Pro»?
- **Punti 5, 6, 10, 11:** budget mensile accettabile per Railway (backup, terzo ambiente) e per una seconda chiave del fornitore.
- **Punto 17:** quanta quota del fornitore resta per l'import delle coppe? Quali coppe mostrare (solo Champions e Europa League, anche le coppe nazionali)?
- **Punto 16:** tono del giornale (ironico come la Gazzetta, neutro?) e chi lo può spegnere (admin della lega?); si possono prendere in giro i partecipanti per nome?; quante notifiche al giorno e a che ora; il giornale è pubblico nella lega o solo per chi lo apre?; regole di priorità per la prima pagina della Master; budget mensile accettabile per il modello e per lo sviluppo; Haiku, Sonnet o Opus dopo una prova su 20-30 edizioni vere.
