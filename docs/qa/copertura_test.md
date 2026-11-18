# Copertura dei test QA e scaletta (web e mobile)

Aggiornato il 18/11/2026 con i circa 30 rapporti delle corse dal 12/11 al 18/11, le correzioni del 18/11 e le prime prove sull'emulatore Android.
**Le corse leggono questo file**: ognuna prova solo le voci **DA FARE** delle sue aree, poi le voci **DA RIVERIFICARE**, e non ripete quelle **OK**. Nel rapporto ogni voce va riportata con il suo codice (es. `3.7`) e l'esito.

## Legenda

- **Piattaforme:** API (solo HTTP); W1280 e W390 (web in Playwright a quella larghezza); MobB (app mobile nel browser, Playwright con Pixel 7); EMU (app Android vera sull'emulatore del PC di Rosario, con Maestro).
- **Stato:**
  - **OK**: verificata, non ripetere;
  - **DA RIVERIFICARE**: corretta da poco, da riprovare su dev;
  - **DA FARE**: mai provata, o mai su quella piattaforma;
  - **APERTO**: difetto noto o da decidere, non segnalarlo di nuovo;
  - **NV**: non verificabile, per il motivo indicato.
- **Prerequisiti:**
  - **[PREP]**: serve la lega preparata (vedi sotto);
  - **[OPER]**: serve un account operatore;
  - **[VIVO]**: serve un turno con calcio d'inizio vicino.

## Prerequisiti da preparare una volta sola

1. **Lega preparata `QA-PREP-PARI`**, da tenere e non cancellare:
   - 8 partecipanti (`qa-01` admin, poi `qa-02`…`qa-08`) e competizioni Serie A, Premier e LaLiga;
   - rose complete a 35 (riempimento casuale o import CSV), lega **attivata**, così ci sono calendario e turni veri.
   - Serve a tutte le voci [PREP]. Le corse possono usarla, ma non devono eliminarla né modificarne le regole.
2. **Lega preparata `QA-PREP-DISPARI`** con 5 partecipanti (`qa-01`…`qa-05`), attivata: serve al calendario dispari dal vivo.
3. **Account operatore QA:** `qa-09@test.fantappero.it` (stessa password degli altri), registrazione chiesta il 18/11 alla sessione del PC; poi Rosario lo promuove a operatore. Finché non è operatore, le voci [OPER] restano NV.
4. **Turno vivo:** il primo calcio d'inizio reale su dev è il **20/11 alle 20:45** (ora di Roma). Ci sono 3 controlli brevi programmati (−2 h, −10 min, +5 min) sulla lega `QA-PREP-PARI`.

## Area 1 – Accesso, profilo, privacy

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 1.1 | Registrazione: campi, email duplicata, risposta generica | OK | API |
| 1.2 | Password comuni o uguali all'email rifiutate (decisione 12) | DA RIVERIFICARE | API, W1280, MobB: corretto 18/11 (`password_too_common`, `password_same_as_email`) |
| 1.3 | Login, logout che chiude subito il token, refresh e catena | OK | API (corretti 18/11) |
| 1.4 | Profilo: nome, nickname (sosia Unicode, punteggiatura) | OK | API |
| 1.5 | Nickname univoco contro un altro account | DA FARE | API: dare un nickname a `qa-07`, poi provarlo con `qa-06` |
| 1.6 | Avatar: solo immagine vera, `nosniff` (decisione 13) | DA RIVERIFICARE | API: PNG con HTML dentro → 400 `invalid_avatar_format`; EMU: avatar scelto dalla galleria |
| 1.7 | Preferenze notifiche, quiet hours, esportazione dati | OK | API |
| 1.8 | Eliminazione account vera | DA FARE | API: con un account usa e getta `qa-tmp-<data>@test.fantappero.it`, mai con `qa-01`…`qa-08` |
| 1.9 | Informativa privacy a schermo | DA FARE | W1280, W390, MobB |
| 1.10 | Rate limit registrazione e login | OK | API |
| 1.11 | Login, logout e sessione dopo il riavvio dell'app | OK | EMU 18/11 (flusso 04) |
| 1.12 | Accesso con email nell'app | OK con riserva | EMU: l'app è OK, ma Maestro 2.10 si blocca a scrivere il testo, quindi l'accesso si fa con adb |
| 1.13 | Link di verifica email e di reset password aperti dall'app | DA FARE | EMU: `adb shell am start -d "fantappero://…"` (deep link) |
| 1.14 | PATCH del nickname in parallelo, token push non cancellati all'eliminazione | APERTO | solo lettura del codice |
| 1.15 | Email reali, accesso con Google, richiesta di accesso dei non tester | NV | su dev |

## Area 2 – Leghe, inviti, partecipanti

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 2.1 | Creazione lega, preset, crediti iniziali, codice invito e adesione | OK | API |
| 2.2 | Invito nominale: accetta, rifiuta, revoca, duplicati | OK | API |
| 2.3 | Gli stessi flussi a schermo | DA FARE | W1280, W390, MobB, EMU |
| 2.4 | Ingresso con link di invito aperto dall'app | DA FARE | EMU: deep link |
| 2.5 | Elenco partecipanti, ruoli, permessi admin e non membro | OK | API |
| 2.6 | Sostituzione partecipante | DA RIVERIFICARE | API (incerto dal 15-16/11) |
| 2.7 | Eliminazione lega da admin (bozza) | OK | API |
| 2.8 | Eliminazione lega da operatore, a schermo | DA FARE [OPER] | W1280, MobB |
| 2.9 | Notifica "Lega eliminata" vista davvero | DA FARE | API e MobB: crea una lega con un membro, eliminala, controlla la notifica del membro |
| 2.10 | Codici 400 invece di 403/404, badge inviti con la lega in asta | APERTO | noto |
| 2.11 | Scadenza reale di un invito | NV | il minimo è 1 giorno |

## Area 3 – Rosa, listone, crediti

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 3.1 | Listone: conteggi e filtro ruolo | OK | API (`?role=` non valido → 200: APERTO, stile) |
| 3.2 | Ricerca senza accenti ("dembele" → "Dembélé") | DA RIVERIFICARE | W1280, W390, MobB, EMU, listoni admin: corretto 18/11 |
| 3.3 | Listone solo con i club dei campionati della lega (decisione 14) | DA RIVERIFICARE | API: corretto 18/11 nel codice; su dev serve un "Aggiorna listone" dell'admin di lega, poi in una lega Liga/Premier/Serie A non devono comparire club tedeschi o francesi né squadre di serie B |
| 3.4 | Override di ruolo: NUL nel motivo → 422 | DA RIVERIFICARE | API |
| 3.5 | Override di ruolo dal turno successivo | DA FARE [PREP] | API |
| 3.6 | Assegnazione slot, limiti 3/11/11/10, crediti | OK | API |
| 3.7 | Admin che porta il prezzo a 0 → rimborso | DA RIVERIFICARE | API |
| 3.8 | Import CSV: nomi ambigui risolvibili, niente `roster_full` sulle righe valide, punto e virgola (decisione 15) | DA RIVERIFICARE | API, W1280 (selettore dei nomi ambigui a schermo) |
| 3.9 | Riempimento casuale | OK | API (lento, circa 6 s) |
| 3.10 | Riempimento IA | NV | manca l'API per creare un fantallenatore IA |
| 3.11 | Movimenti crediti = saldo, storico rosa, esubero in attesa | OK | API |
| 3.12 | Rosa e crediti a schermo con una rosa piena | DA FARE [PREP] | W390, MobB, EMU |

## Area 4 – Mercato: scambi

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 4.1 | Proposta, accetta, rifiuta, annulla, controproposta, scadenza | OK | API |
| 4.2 | Concorrenza (doppia accettazione, deadlock) | OK | API (corretto 18/11) |
| 4.3 | Approvazione dell'admin, notifiche e link | OK | API |
| 4.4 | Rifiuto che chiude il pannello, a schermo | DA FARE | W1280, W390 |
| 4.5 | Filtri Ricevute/Inviate/In corso/Tutte e statistiche, a schermo | DA FARE | W1280, W390, MobB |
| 4.6 | "Non più valida" e "+ N in attesa di crediti", a schermo | DA FARE | W1280, MobB |
| 4.7 | Scambio sbilanciato a rosa piena 35/35 ed esubero di ruolo | DA FARE [PREP] | API |
| 4.8 | Scambi chiusi a turno in corso (`round_freeze`) | DA FARE [PREP][VIVO] | API, il 20/11 sera |
| 4.9 | Proporre uno scambio dall'app e riceverne la notifica | DA FARE [PREP] | EMU |
| 4.10 | Limite proposte aggirabile con l'approvazione admin | APERTO | noto |
| 4.11 | Scambio con un non membro | NV | manca un account esterno |

## Area 5 – Mercato: aste e svincolati

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 5.1 | Buste: sessione, offerta, ritiro, chiusura, risoluzione, spareggio | OK | API (correzioni 16-18/11 da riverificare con la corsa delle 04:13) |
| 5.2 | Spareggio che finisce di nuovo in parità | DA FARE | API |
| 5.3 | Waiver in parità | DA FARE | API |
| 5.4 | Live: manuale, sequenziale, rilanci, timer, aggiudicazione | OK | API |
| 5.5 | Live: giro completo `turn_based` | DA FARE | API |
| 5.6 | Live: leader senza crediti all'aggiudicazione | DA FARE | API |
| 5.7 | Live: scambio immediato a rosa 35/35 | DA FARE [PREP] | API |
| 5.8 | Selettore calciatori dell'asta (buste e live), a schermo | DA FARE | W1280, W390, MobB |
| 5.9 | Avvisi "Spareggio annullato", busta "non assegnabile", "Scelta richiesta: rosa al completo" visti davvero | DA FARE | API e MobB |
| 5.10 | Fare un'offerta in busta dall'app | DA FARE [PREP] | EMU |
| 5.11 | Rimborso del calciatore svincolato con il waiver | APERTO | da decidere |
| 5.12 | Risoluzione concorrente vera | NV | regola: una richiesta alla volta per account |

## Area 6 – Formazione

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 6.1 | Moduli, titolari, panchina, validazioni server | OK | API |
| 6.2 | Bozza: al massimo 11 titolari, 1 portiere e i ruoli del modulo; DELETE solo a turno aperto | DA RIVERIFICARE | API: corretto 18/11 |
| 6.3 | Bloccati, indisponibili, fuori rosa | DA RIVERIFICARE | API (incerto per gli indisponibili reali) |
| 6.4 | Copia formazione precedente | DA RIVERIFICARE | API (incerto) |
| 6.5 | Salvare la formazione a schermo | DA FARE [PREP] | W390, MobB, EMU |
| 6.6 | Esubero di ruolo in formazione | DA FARE [PREP] | API |
| 6.7 | Blocco progressivo, mosse tattiche, formazione automatica al primo blocco | DA FARE [PREP][VIVO] | API, il 20/11 dalle 18:45 alle 20:50 |
| 6.8 | Formazione dell'operatore | DA FARE [OPER] | API |

## Area 7 – Turni, calendario, classifica

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 7.1 | Calendario pari, partite del turno, soglia partite, reinclusione | OK | API |
| 7.2 | Calendario dispari dal vivo | DA FARE [PREP] | API, con `QA-PREP-DISPARI` |
| 7.3 | Attivazione lega: blocco per crediti | DA FARE | API: un partecipante a saldo negativo prima dell'attivazione |
| 7.4 | Cutoff, ricalcolo, apertura manuale del turno, omologazione, correzioni | DA FARE [OPER] | API |
| 7.5 | Notifiche "formazione in scadenza" e "blocco imminente" | DA FARE [PREP][VIVO] | API, MobB |
| 7.6 | Turni, calendario e classifica a schermo con una lega attiva | DA FARE [PREP] | W1280, W390, MobB, EMU |
| 7.7 | Risultati, voti, fantapunti, classifica, scontro diretto | NV | nessuna partita giocata su dev, forse dal 21/11 |

## Area 8 – Notifiche

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 8.1 | Centro notifiche: elenco, segna letta, badge | OK | API |
| 8.2 | "Segna tutte lette" e `limit` | DA RIVERIFICARE | API |
| 8.3 | Generate da invito, scambio e asta | OK | API |
| 8.4 | Link profondo sul web | OK | API |
| 8.5 | Tocco su una notifica di scambio nell'app → Mercato › Scambi | OK | EMU 18/11 |
| 8.6 | Tocco su ogni altro tipo di notifica (asta, turno, invito, fantallenatori, operatore) | DA FARE | MobB, EMU [PREP] |
| 8.7 | Notifica di una lega eliminata: apre Scambi senza lega | APERTO | noto: sul mobile il tocco non cambia la lega attiva |
| 8.8 | Push ed email reali | NV | l'emulatore ha Google APIs senza Play Store, push da verificare su un telefono |

## Area 9 – Web

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 9.1 | Pagine principali senza errori in console e senza scorrimento orizzontale | OK | W1280, W390 |
| 9.2 | Tab Mercato a 390 | DA FARE | W390 |
| 9.3 | Contrasti del tema chiaro e scuro | DA RIVERIFICARE | W1280, W390 |
| 9.4 | Pagine nuove: "+ Tester" con liste impaginate, "Elimina" lega, "Rimetti nel turno" | DA FARE ("+ Tester" ed "Elimina" sono [OPER]) | W1280, W390 |
| 9.5 | Pagine principali con una lega attiva e rose piene | DA FARE [PREP] | W1280, W390 |

## Area 10 – App mobile (browser ed emulatore)

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 10.1 | Schermate principali senza errori | OK su EMU 18/11 (flusso 02, account senza lega); DA FARE su MobB | MobB |
| 10.2 | Schermate principali con contenuti di lega | DA FARE [PREP] | MobB, EMU |
| 10.3 | Pannello operatore mobile | DA FARE [OPER] | MobB, EMU |
| 10.4 | Coerenza con il web: etichette, stati scambi, colori ruolo, causali crediti | DA FARE | MobB contro W390, sulla stessa lega [PREP] |
| 10.5 | Schermata di accesso: tema chiaro, bandiera Premier, tastiera | OK | EMU 18/11 (contrasto di "GIOCA" corretto il 18/11: DA RIVERIFICARE) |
| 10.6 | Galleria e fotocamera per l'avatar | DA FARE | EMU |
| 10.7 | Push vere, Google nativo | NV | serve un telefono vero |

## Area 12 – App Android: azioni sull'app (solo EMU)
Le aree 1-8 sono state provate quasi sempre via API. Qui ci sono le stesse funzioni fatte **dall'app**, più le cose che esistono solo su un telefono. Quando serve l'altra parte (per esempio chi riceve uno scambio), quella si fa via API con un altro account QA.

| Cod | Voce | Stato | Blocco |
|---|---|---|---|
| 12.1 | Registrazione dall'app con un account usa e getta, messaggio di verifica | DA FARE | M1 |
| 12.2 | "Password dimenticata" dall'app | DA FARE | M1 |
| 12.3 | Profilo: nome, nickname, preferenze notifiche, ore di silenzio, tema chiaro e scuro | DA FARE | M1 |
| 12.4 | Esportazione dati ed eliminazione account dall'app (account usa e getta) | DA FARE | M1 |
| 12.5 | Sessione: app in background per più di 30 minuti e ritorno (rinnovo del token), poi riavvio | DA FARE | M1 |
| 12.6 | Creare una lega dall'app (nome, competizioni, regole) | DA FARE | M1 |
| 12.7 | Ingresso con codice; invito nominale ricevuto, accettato e rifiutato | DA FARE | M1 |
| 12.8 | Partecipanti, directory fantallenatori, cambio della lega attiva | DA FARE [PREP] | M1 |
| 12.9 | Listone: filtro ruolo, ricerca, "Solo disponibili" | DA FARE [PREP] | M2 |
| 12.10 | Admin dall'app: assegnazione manuale di uno slot, svincolo con rimborso | DA FARE [PREP] | M2 |
| 12.11 | Scambi dall'app: proponi, accetta, rifiuta, annulla, controproposta | DA FARE [PREP] | M2 |
| 12.12 | Approvazione admin di uno scambio dall'app | DA FARE [PREP] | M2 |
| 12.13 | Asta a buste dall'app: offerta, ritiro, esito | DA FARE [PREP] | M2 |
| 12.14 | Asta live dall'app: rilancio, timer, aggiudicazione (gli altri rilanciano via API) | DA FARE [PREP] | M2 |
| 12.15 | Movimenti crediti e causali | DA FARE [PREP] | M2 |
| 12.16 | Formazione: modulo, titolari, panchina e ordine, bozza, copia della precedente | DA FARE [PREP] | M3 |
| 12.17 | Calciatori bloccati o indisponibili visibili ma non selezionabili | DA FARE [PREP] | M3 |
| 12.18 | Turni europei, calendario, scontro diretto, classifica | DA FARE [PREP] | M3 |
| 12.19 | Centro notifiche: badge, segna letta, segna tutte lette | DA FARE | M4 |
| 12.20 | Preferenze notifiche e ore di silenzio rispettate | DA FARE | M4 |
| 12.21 | Tasto "indietro" di Android su ogni schermata: non esce dall'app per sbaglio e non perde i dati inseriti | DA FARE | M5 |
| 12.22 | Accessibilità: testo grande (scala 1,3) e TalkBack sui pulsanti principali | DA FARE | M5 |
| 12.23 | Rete assente o lenta (modalità aereo): messaggi d'errore e ripresa | DA FARE | M5 |
| 12.24 | Tema chiaro e scuro su tutte le schermate principali | DA FARE | M5 |
| 12.25 | Schermo più piccolo: l'AVD `maestro_e2e` (Pixel 5) | DA FARE | M5 |

## Area 11 – Salute e prestazioni

| Cod | Voce | Stato | Dove / note |
|---|---|---|---|
| 11.1 | `/live`, `/ready`, letture sotto 2 s, nessun 5xx | OK | API (scritture lente: sincronizza 9,5 s, assegnazioni fino a 5,4 s, riempimento 6 s) |
| 11.2 | Tempi su una lega attiva con rose piene | DA FARE [PREP] | API |
| 11.3 | `/realtime/stream` | DA FARE | API: si apre, riceve un evento dopo un'azione e si chiude senza errori |

## Scaletta

### Notte (6 corse cloud, dalle 22:23 alle 04:13)
Ogni corsa prova, nelle sue aree, prima le voci DA FARE senza prerequisiti mancanti, poi le DA RIVERIFICARE. Se le restano risorse, ripassa quelle con il prerequisito appena pronto.

| Corsa | Aree | Voci previste per la prossima notte |
|---|---|---|
| 22:23 Mercato | 4, 5 | 5.2, 5.3, 5.5, 5.6, 5.9; con [PREP]: 4.7, 5.7 |
| 23:33 Gruppo A | 1, 2 | 1.2, 1.5, 1.6, 1.8, 1.9, 2.3 (W), 2.6, 2.9 |
| 00:43 Gruppo B | 3, 6 | 3.2, 3.3, 3.4, 3.7, 3.8, 6.2, 6.3, 6.4; con [PREP]: 3.5, 6.6 |
| 01:53 Gruppo C | 7, 8 | 7.3, 8.2; con [PREP]: 7.2, 7.6 |
| 03:03 Gruppo D | 9, 10, 11 | 9.2, 9.3, 4.4, 4.5, 4.6, 5.8 (W e MobB), 10.1 MobB, 1.9 MobB, 11.3; con [PREP]: 9.5, 10.2, 10.4, 11.2 |
| 04:13 Verifica | tutte | regressioni: le voci "CORRETTI" degli ultimi 3 giorni di `known_issues.md` |

### Mobile di giorno: emulatore Android sul PC di Rosario (dalle 8 alle 22)
Le corse mobile vere si fanno di giorno, quando Rosario è disponibile. Le esegue la sessione aperta sul suo PC ("rosario-graceful-feigenbaum") con l'app installata sull'emulatore, Maestro e `adb`, contro l'API di dev. Quella sessione le avvia da sola con un timer locale (`CronCreate`) e scrive il rapporto nella sua chat.
- **Regole per tutti i blocchi:**
  - account `qa-02` (e `qa-03` per gli scambi), lega `QA-PREP-PARI`;
  - prima di ogni blocco `git pull` su `main`;
  - si provano solo le voci del blocco ancora DA FARE o DA RIVERIFICARE nella colonna EMU.
- **Build:** se `main` ha modifiche in `apps/mobile` o `packages`, si ricompila l'APK prima del blocco, solo a emulatore spento (insieme non stanno nei 16 GB di RAM) e senza altre build in corso sul PC.
- **Se il PC è spento** o la sessione non è aperta, il blocco salta e lo recupera quello successivo.

| Ora (Roma) | Blocco | Voci del registro |
|---|---|---|
| 08:30 | M1 Accesso, account e leghe | 1.12, 1.13, 1.9, 10.5, 10.6, 2.3, 2.4, 12.1-12.8 |
| 11:30 | M2 Rosa e mercato | 3.2, 3.12, 4.5, 4.6, 4.9, 5.8, 5.10, 12.9-12.15 |
| 14:30 | M3 Formazione e turni | 6.5, 7.6, 10.2, 12.16-12.18 |
| 17:30 | M4 Notifiche | 8.6, 12.19, 12.20, e le notifiche nate dalle prove di M2 e M3 |
| 20:30 | M5 Sistema e ripasso | 12.21-12.25, poi tutti i flussi Maestro di `apps/mobile/e2e/maestro/flows/dev/` sull'ultimo APK (regressione mobile del giorno) |

Ogni blocco dura al massimo un'ora circa: le voci che non riesce a fare passano al giorno dopo, finché nel registro non restano voci DA FARE per quel blocco. Quando un blocco non ha più voci DA FARE, fa solo il ripasso dei flussi Maestro.

Il **20/11** il blocco delle 20:30 si sposta alle **20:40**: guarda sull'app il blocco progressivo della partita delle 20:45 (6.7, EMU).

Restano alle corse notturne (cloud):
- l'app mobile **nel browser** (MobB, corsa delle 03:03);
- la **coerenza con il web** a 390 px (10.4), perché lì web e app si aprono nello stesso browser.

Restano NV sul mobile: push vere e accesso con Google (10.7), perché l'emulatore non ha Play Store, e il pannello operatore (10.3) finché non c'è `qa-09` operatore.

**Prerequisiti, una volta sola:**
1. Maestro dalla 2.10.0 alla 2.12.x;
2. creare `QA-PREP-PARI` e `QA-PREP-DISPARI`;
3. registrare `qa-09`, che Rosario poi promuove a operatore.

### Turno vivo, 20/11 (lega `QA-PREP-PARI`)
Tre controlli brevi, alle 18:45, alle 20:35 e alle 20:50 ora di Roma: 4.8, 6.7, 7.5.

### Dopo il 21/11
7.7 (risultati e voti), se su dev arrivano i dati delle partite giocate.

## Come si aggiorna questo file
Ogni mattina, dopo il riepilogo delle 06:17, le voci coperte nella notte cambiano stato: OK, APERTO (con la voce in `known_issues.md`) o NV con il motivo. Le corse non scrivono nel repository: aggiorna la sessione che coordina il lavoro. Quando un'area non ha più voci DA FARE o DA RIVERIFICARE, la sua corsa notturna si può spegnere per risparmiare.
