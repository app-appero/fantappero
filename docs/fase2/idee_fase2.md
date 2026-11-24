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

## 4. Domande da fare a Rosario all'apertura della Fase 2
- **Punto 12:** «piene funzionalità» vuol dire che l'operatore può anche cambiare cose (regolamento, formazioni, mercato) o solo vedere tutto? I membri della lega devono vedere che l'operatore è entrato (registro, avviso)?
- **Punto 13:** come si entra nella Master (iscrizione libera, a pagamento, su invito)? Regole diverse dalle leghe normali?
- **Punto 14:** le leghe devono poter essere «aperte alle richieste» con un'opzione dell'admin, così non tutte compaiono in elenco? Cosa vede chi cerca una lega (nome, campionati, posti liberi, regolamento)?
- **Punto 15:** classifica dei **fantallenatori** (vince il singolo con più fantapunti fra tutte le leghe) o delle **leghe** (vince la lega con più punti sommando i suoi fantallenatori)? Nel secondo caso le leghe con più squadre partono avvantaggiate: meglio la media per squadra. Che premio, e chi lo assegna?
- **Punto 8:** cosa resta gratis e cosa diventa «Pro»?
- **Punti 5, 6, 10, 11:** budget mensile accettabile per Railway (backup, terzo ambiente) e per una seconda chiave del fornitore.
