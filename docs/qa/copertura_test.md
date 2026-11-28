# Copertura dei test QA e scaletta (web e mobile)

Aggiornato il 24/11/2026 (prima: 23/11, 22/11 e 18/11) con:
- i blocchi M1-M5 del 23/11 sull'emulatore del PC di Rosario (M2 tutto NV per il fermo di Railway; M4 e M5 con l'APK dev che contiene le correzioni dell'app della 1.4);
- le cinque corse della notte 23→24/11 (22:23, 23:33, 00:43, 03:03 e 04:13; il Gruppo C quella notte non parte);
- `known_issues.md` al 24/11 (righe fino a KI-165): le correzioni del 23/11 riprovate nella notte, le decisioni di Rosario del 23 e 24/11 e i problemi nuovi della notte 23→24/11.

Prima, il 23/11: i blocchi M3-M5 del 22/11 e le cinque corse della notte 22→23/11. Il 22/11: i rapporti del 21/11 e le corse delle notti 20→21/11 e 21→22/11.

Il 28/11 si aggiunge l'**Area 13** (release 1.5: allineamento app ↔ sito e conferme), tutta DA FARE: MobB per l'app, W1280 e W390 per le conferme del sito (13.2, 13.3), EMU con un APK 1.5.

**Le corse leggono questo file**: ognuna guarda la colonna della sua piattaforma e prova solo le voci **DA FARE** delle sue aree, poi le **DA RIVERIFICARE**, e non ripete quelle **OK**. Nel rapporto ogni voce va riportata con il suo codice (es. `3.7`), la piattaforma e l'esito.

## Legenda

- **Piattaforme (colonne):** API (solo HTTP); W1280 e W390 (web in Playwright a quella larghezza); MobB (app mobile nel browser, Playwright con Pixel 7); EMU (app Android vera sull'emulatore del PC di Rosario, con Maestro).
- **Stato, piattaforma per piattaforma:**
  - **OK**: verificata, non ripetere;
  - **DA RIVERIFICARE**: corretta o uscita da poco, da riprovare su dev;
  - **DA FARE**: mai provata, o mai su quella piattaforma;
  - **APERTO**: difetto noto o da decidere, non segnalarlo di nuovo;
  - **NV**: non verificabile, per il motivo indicato;
  - **–**: la voce non riguarda quella piattaforma.
- **Ultima:** data dell'ultima prova (per le corse notturne, la data del piano: la notte 21→22/11 è il 22/11; la corsa 22:23 porta invece la data della sera). «12-18/11» vuol dire provata fra il 12 e il 18/11.
- **KI-N:** riga N della tabella di `known_issues.md` (numero di riga del file al 24/11).
- **Prerequisiti:**
  - **[PREP]**: serve la lega preparata (vedi sotto);
  - **[OPER]**: serve un account operatore;
  - **[VIVO]**: serve un turno con calcio d'inizio vicino.

## Riepilogo al 24/11

Giudizio per voce: **fatto** se tutte le piattaforme che la riguardano sono OK; **problema aperto** se almeno una è APERTO; **da ricontrollare** se almeno una è DA RIVERIFICARE; **manca** se almeno una è DA FARE; **non verificabile** se il resto è NV.

| Area | Voci | Fatto | Manca | Da ricontrollare | Problema aperto | Non verificabile |
|---|---|---|---|---|---|---|
| 1. Accesso, profilo, privacy | 16 | 14 | 0 | 0 | 1 | 1 |
| 2. Leghe, inviti, partecipanti | 12 | 9 | 0 | 0 | 2 | 1 |
| 3. Rosa, listone, crediti | 15 | 13 | 0 | 1 | 0 | 1 |
| 4. Mercato: scambi | 13 | 8 | 3 | 0 | 1 | 1 |
| 5. Mercato: aste e svincolati | 13 | 8 | 2 | 1 | 1 | 1 |
| 6. Formazione | 10 | 7 | 3 | 0 | 0 | 0 |
| 7. Turni, calendario, classifica | 8 | 5 | 1 | 2 | 0 | 0 |
| 8. Notifiche | 9 | 8 | 0 | 0 | 0 | 1 |
| 9. Web | 5 | 4 | 0 | 1 | 0 | 0 |
| 10. App mobile (browser ed emulatore) | 11 | 8 | 1 | 0 | 1 | 1 |
| 11. Salute e prestazioni | 3 | 3 | 0 | 0 | 0 | 0 |
| 12. App Android: azioni sull'app (solo EMU) | 25 | 20 | 5 | 0 | 0 | 0 |
| **Totale** | **140** | **107** | **15** | **5** | **6** | **7** |
| Totale al 18/11 | 124 | 33 | 66 | 12 | 5 | 8 |

Il 25/11 entrano 4.12, 4.13 e 10.11 (sostituto dopo uno scambio sbilanciato, 1.5): tutte DA FARE appena pubblicate su dev; nell'app sull'emulatore con l'APK 1.5.

La sera del 25/11 4.13 (W1280, W390) e 10.11 (MobB) passano a DA RIVERIFICARE per i 3 avvisi nuovi suggeriti dalla corsa Mercato (crediti che non bastano per il sostituto, testo della controproposta, ruoli sotto quota con la rosa piena), da riprovare appena pubblicati su dev.

Il 28/11 entrano 6.9, 6.10, 7.9 e 7.10 (correzioni della 1.5 segnalate da Rosario il 27/11: contatore dei titolari nel tema scuro, ruolo in panchina e tribuna nell'app, testi in italiano nei turni europei, pagina dei turni europei a 390 px): tutte DA FARE appena pubblicate su dev; nell'app sull'emulatore con l'APK 1.5.

Il 28/11 entra anche 7.11 (gol o assist annullato dal VAR che lasciava il bonus, correzione del server): DA FARE su API, W390 e MobB appena pubblicata su dev.

Il 28/11 entra anche 11.4 (area job/Operatore: giro delle formazioni probabili che non partiva alle 07:00 UTC, correzione del server): DA FARE su API e W1280 appena pubblicata su dev.

**Problemi nuovi della notte 23→24/11:**
- **KI-165**, corsa 23:33, voce 2.3 (W1280 e W390; stesso testo e stesso schema nell'app), bassa, in correzione il 24/11 con l'approvazione di Rosario:
  - «Servono ancora 1 iscritti» al plurale (atteso «Serve ancora 1 iscritto»);
  - dopo un invito doppio o una revoca da una scheda non aggiornata, il conto «· 1 invito in attesa» e l'avviso del mercato restano vecchi;
- corsa 04:13, voce 10.10 (solo MobB), non ancora in `known_issues.md`: nell'app aperta nel browser, dopo il cambio tema il Profilo torna in cima (la correzione 377b0a3 della 1.4 non tiene); sull'emulatore resta dov'era (M4 del 23/11).

Da decidere (osservazione, non un difetto confermato): il contrasto del blu della pastiglia «provvisorio» sul campo, 3,68:1 sul secondo colore del gradiente, visto solo con una pastiglia finta (voce 9.3).

Le correzioni del 23/11 sono pubblicate su dev e riprovate OK nella notte 23→24/11: KI-147 (3.12), KI-148 (2.7), KI-149 (10.1), KI-150 (5.9), KI-123 (10.2) e KI-151 (9.3, tranne «provvisorio»). Sull'emulatore, con l'APK dev della 1.4, sono OK anche KI-142 (12.23), KI-134 (12.18) e KI-155 (10.10).

## Prerequisiti da preparare una volta sola

1. **Lega preparata `QA-PREP-PARI`** (PRONTA dal 18/11: id `d96590b8-37e2-4eff-9f7b-e24dccf8370d`, attiva, 8 × 35, 31 turni europei, 21 giornate; rose fatte con l'import CSV, perché il riempimento casuale vale solo per i fantallenatori IA), da tenere e non cancellare:
   - 8 partecipanti (`qa-01` admin, poi `qa-02`…`qa-08`) e competizioni Serie A, Premier e LaLiga;
   - rose complete a 35, lega **attivata**, così ci sono calendario e turni veri;
   - serve a tutte le voci [PREP]. Le corse possono usarla, ma non devono eliminarla né modificarne le regole;
   - **il turno #11 è omologato su dev dall'1:12 del 24/11** (dalle 23:01 all'1:02 il fornitore rifiutava tutte le chiamate: quota giornaliera finita). Il mercato dovrebbe quindi essere aperto dalla corsa 22:23 del 24/11: si possono provare 4.7, 5.7, 5.10 e 12.10-12.14 (prima controllare che `GET …/mercato/stato` non dia più `marketBlockedReason`).
2. **Lega preparata `QA-PREP-DISPARI`** (PRONTA dal 18/11: id `7a1b25b2-acfc-4ff3-a433-8056a7766330`, attiva, 5 × 35) con 5 partecipanti (`qa-01`…`qa-05`): serve al calendario dispari dal vivo.
3. **Account operatore QA:** `qa-09@test.fantappero.it` (stessa password degli altri), PRONTO dal 18/11: le voci [OPER] si provano con `qa-09`.
4. **Turno vivo:** il prossimo è il **#12**, primo calcio d'inizio il **27/11 alle 20:45** (ora di Roma), blocco della formazione alle **20:30**. In `QA-PREP-DISPARI` riposa `qa-02` nella giornata 12.
5. **Pulizia:** su dev restano tre leghe di prova attive di corse passate: `QA-2026-11-19-0153-B` e `QA-2026-11-21-0413-B` (admin `qa-01`) e `QA-2026-11-21-0043-B` (admin `qa-05`, con `qa-07` tra i membri). Le può eliminare l'operatore `qa-09`. `QA-2026-11-21-0043-B` è oggi l'unica lega con un calciatore in esubero (la usa la corsa 04:13 per «In esubero»): prima di eliminarla, decidere se tenerla.

## Area 1 – Accesso, profilo, privacy

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Registrazione: campi, email duplicata, risposta generica | OK | – | – | – | – | 12-18/11 |  |
| 1.2 | Password comuni o uguali all'email rifiutate (decisione 12) | OK | OK | – | OK | – | 24/11 | API OK il 22/11 (corsa 23:33): `password_too_common`, `password_same_as_email` anche in maiuscolo; nel reset la password comune è rifiutata prima del controllo del token. MobB OK il 23/11 (corsa 03:03). W1280 OK il 24/11 (corsa 23:33): in registrazione i due messaggi a schermo, anche con l'email in maiuscolo. Sito e app non hanno il cambio password dal profilo. Uguale all'email nel reset: NV, serve un token vero |
| 1.3 | Login, logout che chiude subito il token, refresh e catena | OK | – | – | – | – | 22/11 | riprovato il 22/11 |
| 1.4 | Profilo: nome, nickname (sosia Unicode, punteggiatura) | OK | – | – | – | – | 22/11 | 22/11: nickname cirillico e nome oltre 80 caratteri rifiutati (sul profilo 400 invece di 422: solo incoerenza, suggerimento) |
| 1.5 | Nickname univoco contro un altro account | OK | – | – | – | – | 22/11 | rifiutati anche maiuscole, larghezza piena, spazi, accenti e NFD (`nickname_taken`); il nickname lasciato torna libero |
| 1.6 | Avatar: solo immagine vera, `nosniff` (decisione 13) | OK | – | – | – | OK | 23/11 | API OK il 22/11: PNG con HTML → 400 `invalid_avatar_format`, script accodato tolto, servito con `nosniff`. EMU OK il 23/11 (M1): foto scelta dalla galleria salvata e poi rimossa |
| 1.7 | Preferenze notifiche, quiet hours, esportazione dati | OK | – | – | – | – | 22/11 | 22/11: un PATCH rifiutato non salva nulla; preferenze per categoria ed evento rispettate (corsa 01:53) |
| 1.8 | Eliminazione account vera | OK | – | – | – | – | 22/11 | account usa e getta: senza password `invalid_password`, con la password eliminato, poi login 401 e nickname libero. Dall'app: 12.4 |
| 1.9 | Informativa privacy a schermo | – | OK | OK | OK | OK | 21/11 | W1280 e W390 il 21/11 (link in accesso e registrazione, margini di `/privacy`); MobB 21/11 (corsa 03:03); EMU 21/11 (M1, versione 2026-11c) |
| 1.10 | Rate limit registrazione e login | OK | – | – | – | – | 12-18/11 |  |
| 1.11 | Login, logout e sessione dopo il riavvio dell'app | – | – | – | – | OK | 23/11 | flusso 04 passato il 21 e il 22/11 (M5) e il 23/11 (M3, M4 e M5) |
| 1.12 | Accesso con email nell'app | – | – | – | – | OK | 23/11 | flusso 01 passato più volte dal 21/11, l'ultima il 23/11 (M3, M4 e M5) |
| 1.13 | Link di verifica email e di reset password aperti dall'app | – | – | – | – | OK | 18/11 | APK `2633ca4`: link `fantappero://…` e App Link dev `verified`, anche a freddo dal link web |
| 1.14 | PATCH del nickname in parallelo, token push non cancellati all'eliminazione | APERTO | – | – | – | – | 12-18/11 | noto dalla sola lettura del codice (nessuna riga in `known_issues.md`) |
| 1.15 | Email reali, accesso con Google, richiesta di accesso dei non tester | NV | – | – | – | – | – | su dev: email non reali e modalità test spenta (non va accesa) |
| 1.16 | **Nuova (21/11, KI-107).** Informativa accettata anche con l'accesso con email | OK | OK | – | OK | OK | 24/11 | API 22/11 (`policyVersion` dopo l'accesso con email) e 24/11 (corsa 04:13: informativa 2026-11d della 1.4); EMU 21/11; MobB 23/11 (corsa 03:03). W1280 OK il 24/11 (corsa 23:33): nel profilo «Hai accettato l'informativa privacy (versione 2026-11d)…» dopo l'accesso con email |

## Area 2 – Leghe, inviti, partecipanti

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 2.1 | Creazione lega, preset, crediti iniziali, codice invito e adesione | OK | – | – | – | – | 22/11 | rifatto in ogni corsa per preparare le leghe di prova; il mercato resta chiuso finché la lega non è al completo (KI-93) |
| 2.2 | Invito nominale: accetta, rifiuta, revoca, duplicati | OK | – | – | – | – | 22/11 | 22/11: «Annulla invito» toglie la notifica; posti riservati agli inviti in attesa (`league_full`); notifiche d'invito senza doppioni |
| 2.3 | Gli stessi flussi a schermo | – | APERTO | APERTO | APERTO | APERTO | 24/11 | EMU OK il 21/11 (M1); MobB OK il 23/11 (corsa 03:03); W1280 e W390 il 24/11 (corsa 23:33): creazione, codice, invito nominale rifiutato e poi accettato, annullamento, invito doppio, ruoli e conteggi OK. APERTO KI-165 (bassa, in correzione il 24/11): «Servono ancora 1 iscritti» al plurale; dopo un invito doppio o una revoca da una scheda non aggiornata il conto «· 1 invito in attesa» e l'avviso del mercato restano vecchi. Stesso testo e stesso schema nell'app: da riprovare anche su MobB ed EMU (con un APK nuovo) |
| 2.4 | Ingresso con link di invito aperto dall'app | – | – | – | – | OK | 18/11 | da collegato e da scollegato; il link web apre direttamente l'app |
| 2.5 | Elenco partecipanti, ruoli, permessi admin e non membro | OK | – | – | – | – | 22/11 | 22/11: un membro riceve 403 su tutte le azioni da admin |
| 2.6 | Sostituzione partecipante | OK | – | – | – | – | 22/11 | squadra, rosa e crediti passano al nuovo; il vecchio riceve 403; l'invito pendente del nuovo si chiude. Da decidere: chi è stato sostituito può rientrare col codice se resta un posto |
| 2.7 | Eliminazione lega da admin (bozza) | OK | – | – | OK | OK | 24/11 | API OK il 22/11. KI-148 corretto (9568f16): EMU OK il 23/11 (M1: «Elimina lega» con conferma; M4: l'indietro non torna più sulla lega eliminata); MobB OK il 24/11 (corse 03:03 e 04:13: 204, poi la Home di un'altra lega, nessuna schermata d'errore) |
| 2.8 | Eliminazione lega da operatore, a schermo [OPER] | – | OK | – | – | OK | 23/11 | W1280 il 22/11 con qa-09 (il 21/11 anche conferma e annulla, a 1280 e 390). EMU OK il 23/11 (M1): qa-09 elimina una lega dal pannello operatore dell'app, con conferma (KI-68). MobB non conta: la conferma usa `Alert.alert`, che nel browser non si apre (NV il 23/11) |
| 2.9 | Notifica "Lega eliminata" vista davvero | OK | OK | – | OK | – | 23/11 | API e W1280 il 22/11: una notifica per membro, nessuna a chi elimina, preferenza spenta rispettata, link `/`. MobB OK il 23/11 (corsa 03:03) |
| 2.10 | Codici 400 invece di 403/404, badge inviti con la lega in asta | APERTO | – | – | – | – | 12-18/11 | KI-11 (stile, nessuna fuga di dati) |
| 2.11 | Scadenza reale di un invito | NV | – | – | – | – | – | il minimo è 1 giorno |
| 2.12 | **Nuova (22/11).** Notifica «Nuovo invito» tolta quando la lega viene eliminata | OK | – | – | – | – | 24/11 | difetto P1 del 22/11 corretto (KI-119) e riprovato OK il 23 e il 24/11 (corse 04:13): «Nuovo invito» tolto e «Lega eliminata» ricevuta dall'invitato |

## Area 3 – Rosa, listone, crediti

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 3.1 | Listone: conteggi e filtro ruolo | OK | – | – | – | – | 12-18/11 | `?role=` non valido → 200: stile, non segnalare |
| 3.2 | Ricerca senza accenti ("dembele" → "Dembélé") | OK | OK | OK | OK | OK | 23/11 | listone della lega OK su API, W1280, W390 e MobB (21-22/11) ed EMU (21/11, M2). Listone dell'operatore `/admin/listone` OK il 23/11 con qa-09 (corsa 00:43: «dembele», «DEMBELE», «Dembélé», «jovanovic», «o'shea») |
| 3.3 | Listone solo con i club dei campionati della lega (decisione 14) | OK | – | – | – | – | 22/11 | 22/11: dopo «Aggiorna listone» nessun club fuori da Serie A, Liga e Premier. I rientrati dal prestito (Mandas, KI-109) ricompaiono solo dopo «Aggiorna listone» |
| 3.4 | Override di ruolo: NUL nel motivo → 422 | OK | – | – | – | – | 22/11 |  |
| 3.5 | Override di ruolo dal turno successivo [PREP] | OK | – | – | – | – | 21/11 | il 21/11 valeva dal turno 1 se mancava `currentRound` (corsa 00:43): corretto il 21/11 (KI-100) e riprovato OK lo stesso giorno. Resta il limite noto KI-66: rosa e mercato mostrano il ruolo ufficiale |
| 3.6 | Assegnazione slot, limiti 3/11/11/10, crediti | OK | – | – | – | – | 22/11 | 22/11: rifiuto a ruolo pieno con lo stesso conteggio del server (KI-113) |
| 3.7 | Admin che porta il prezzo a 0 → rimborso | OK | – | – | – | – | 22/11 |  |
| 3.8 | Import CSV: nomi ambigui risolvibili, niente `roster_full` sulle righe valide, punto e virgola (decisione 15) | OK | OK | – | – | – | 22/11 | API 22/11; W1280 21/11 (scelta dei nomi ambigui a schermo). La conferma rifiutata che salvava le scelte (21/11) è corretta (KI-100) e riprovata OK. Import da Excel: NV, manca lo strumento |
| 3.9 | Riempimento casuale | OK | – | – | – | – | 12-18/11 | lento, circa 6 s |
| 3.10 | Riempimento IA | NV | – | – | – | – | – | manca l'API per creare un fantallenatore IA |
| 3.11 | Movimenti crediti = saldo, storico rosa, esubero in attesa | OK | – | – | – | – | 24/11 | 23/11 (corse 00:43 e 04:13): saldo = saldo ricostruito = somma dei movimenti per 22 squadre; note dei movimenti, vecchie e nuove, con i nomi giusti («Acquisto L. Jovanović», «Acquisto D. O'Shea»): D1 del 22/11 corretto (KI-118), riprovato OK il 24/11 (corsa 04:13: 54 note con accenti o apostrofi, nessuna rovinata). Note vecchie rovinate da riparare in lettura: NV, non ce ne sono più |
| 3.12 | Rosa e crediti a schermo con una rosa piena [PREP] | – | OK | OK | OK | OK | 24/11 | i difetti del 21/11 sono corretti (KI-100, KI-104) e riprovati OK il 21-22/11; MobB ed EMU 21/11 (M2). KI-147 corretto (6488c3a): il 24/11 (corse 00:43 e 04:13) a 390 la tabella «Intervalli di possesso» di Rosa › Storico scorre nel suo riquadro e «Al» e «Fonte» si raggiungono, per membro e admin; a 1280 nessuno scorrimento. «In esubero» al posto di «In attesa» (decisione per la 1.4) OK sul sito |
| 3.13 | **Nuova (21/11, KI-106 e KI-112).** Listone: filtri «Campionato» e «Squadra», «Azzera filtri» | – | OK | OK | OK | OK | 23/11 | W1280 OK il 22/11 (corsa 04:13); EMU OK il 22/11 (M3, «Azzera filtri» riporta anche il ruolo, KI-112); W390 e MobB OK il 23/11 (corse 00:43 e 03:03). «Azzera filtri» lascia ricerca e «Solo disponibili» per scelta (KI-138). Menu «Campionato» nascosto con un solo campionato: NV, una lega ne richiede almeno 3. I filtri sono solo su sito e app, non nell'API; non ancora nel listone dell'operatore |
| 3.14 | **Nuova (21/11, KI-113).** Avviso quando un ruolo è al completo | OK | OK | OK | OK | OK | 23/11 | API 22/11: rifiuto a ruolo pieno, conteggio uguale al server. EMU 21/11 (APK `04cc83b`): «Portieri al completo: 3 su 3…», swipe bloccato con il motivo, il ruolo torna libero dopo lo svincolo. W1280, W390 e MobB OK il 23/11 (corsa 00:43, portieri 3/3 con altri posti liberi): avviso per membro e admin, «+» disattivati con il motivo, swipe «Pieno» su MobB |
| 3.15 | **Nuova (23/11, 1.3, KI-141).** Media stagionale, Valore di mercato e carriera nel listone e nella scheda del calciatore | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | OK | 23/11 | EMU OK il 23/11 (M1: media, Valore e carriera di un portiere; M4: «Dettaglio del Valore» nel pannello operatore). Da provare su API, sito e MobB: media della stagione in corso e della scorsa, Valore sul ruolo ufficiale, coppe solo nella carriera (KI-145) |

## Area 4 – Mercato: scambi

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 4.1 | Proposta, accetta, rifiuta, annulla, controproposta, scadenza | OK | – | – | – | – | 12-18/11 |  |
| 4.2 | Concorrenza (doppia accettazione, deadlock) | OK | – | – | – | – | 18/11 | corretto il 18/11 |
| 4.3 | Approvazione dell'admin, notifiche e link | OK | – | – | – | – | 12-18/11 |  |
| 4.4 | Rifiuto che chiude il pannello, a schermo | – | OK | OK | – | – | 21/11 | corsa 03:03 del 21/11, anche la controproposta |
| 4.5 | Filtri Ricevute/Inviate/In corso/Tutte e statistiche, a schermo | – | OK | OK | OK | OK | 21/11 |  |
| 4.6 | "Non più valida" e "+ N in attesa di crediti", a schermo | – | OK | OK | OK | – | 21/11 |  |
| 4.7 | Scambio sbilanciato a rosa piena 35/35 ed esubero di ruolo [PREP] | DA FARE | – | – | – | – | – | non si poteva fare il 22/11 né la sera del 23/11 (corsa 22:23): il turno 11 di `QA-PREP-PARI` era ancora bloccato, scambi fermi (`market_round_in_progress`). Il turno 11 è omologato dall'1:12 del 24/11: da fare prima del blocco del 27/11. Stato della rosa coerente su `/rosa` e `/squadre` |
| 4.8 | Scambi chiusi a turno in corso (`round_freeze`) | OK | OK | OK | OK | OK | 22/11 | API 22/11: proposta, accettazione e controproposta → 400 `market_round_in_progress`; a schermo il 21/11 «Mercato fermo: turno in corso» (KI-102) su sito, MobB ed EMU |
| 4.9 | Proporre uno scambio dall'app e riceverne la notifica | – | – | – | – | OK | 18/11 | il 21/11 il flusso 07 è fallito solo perché il mercato era fermo |
| 4.10 | Limite proposte aggirabile con l'approvazione admin | APERTO | – | – | – | – | 12-18/11 | KI-21, da decidere |
| 4.11 | Scambio con un non membro | NV | – | – | – | – | – | manca un account esterno |
| 4.12 | **Nuova (25/11, 1.5).** Sostituto dopo uno scambio sbilanciato, regole del server [PREP] | OK | – | – | – | – | 25/11 | corsa Mercato lanciata a mano il 25/11: OK; resta da provare il rifiuto a turno in corso (`market_round_in_progress`) dopo il blocco del 27/11. uno scambio 2 per 1 eseguito (accettato, o approvato se la lega lo chiede) crea un sostituto da scegliere per chi resta a 34/35 (`GET …/mercato/sostituti`); `GET …/mercato/sostituti/liberi` dà solo i liberi del ruolo che manca, con `marketValue` come prezzo; `POST …/mercato/sostituti/acquista` compra al Valore anche a mercato chiuso, scala i crediti («Sostituto dopo lo scambio: <nome>») e la formazione torna salvabile. Rifiutati: ruolo sbagliato, crediti insufficienti, libero già preso, squadra corta senza scambio (`replacement_not_available`), turno in corso (`market_round_in_progress` con il turno). Le proposte aperte hanno `proposerRosterAfter` / `recipientRosterAfter`. Notifica «Scegli il sostituto dopo lo scambio» a chi non ha accettato. Da fare fuori dal turno in corso |
| 4.13 | **Nuova (25/11, 1.5).** Sostituto dopo uno scambio sbilanciato, a schermo [PREP] | – | DA RIVERIFICARE | DA RIVERIFICARE | – | – | 25/11 | **DA RIVERIFICARE per i 3 avvisi nuovi della sera del 25/11** (suggerimenti della corsa, nessuna regola cambia): 1) crediti che non bastano: con un 2 per 1 che lascia la squadra con meno crediti del libero più economico del ruolo che manca (anche offrendo crediti nello scambio), sotto il riquadro arancione «Attenzione: dopo lo scambio avrai N crediti e il Difensore libero più economico costa M. Da solo non potrai prendere il sostituto: dovrà assegnartelo l'admin.» (all'admin in terza persona con il nome della squadra), lo scambio si fa lo stesso; nella finestra «Scegli il sostituto» il riquadro «Nessun libero alla tua portata: hai N crediti e il più economico costa M. Chiedi all'admin di assegnarti un Difensore.» e l'elenco tutto grigio; 2) controproposta che lascia corti: «Inviare la controproposta?» / «Invia controproposta» (la proposta nuova resta «Proporre lo scambio?» / «Proponi scambio»); 3) 1 per 1 tra ruoli diversi a rosa 35/35: riga «Dopo lo scambio avrai 10 Centrocampisti su 11.» in un riquadro giallo (con giocatori mancanti, nell'arancione: «Anche con il sostituto avrai…»), in Rosa il riquadro «Ruoli sotto quota: 10 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.» (non con i sostituti da scegliere), e dopo l'ultimo sostituto lo stesso testo nella conferma e nell'avviso. Prima: corsa Mercato lanciata a mano il 25/11: OK. «Accetta» su un 2 per 1: riquadro arancione «Dopo lo scambio avrai 34/35 · Ti mancherà un Difensore…», pulsanti «Annulla» / «Accetta e scegli», poi «Scegli il sostituto» (riquadro verde «Scambio fatto: è arrivato <nome>», etichette Rosa/Crediti/Solo, ricerca, ordine per Valore, «Prendi · N», chi costa troppo grigio «Costa più dei tuoi crediti», «Più tardi»), conferma con il conto (Crediti ora, Valore di <nome> − N, Ti restano). Stesso avviso a chi propone (prima di inviare) e all'admin che approva (con il nome della squadra). Con «Più tardi»: riquadro «Rosa incompleta: 34/35» in Rosa e Formazione, «Salva formazione» spento con la nota sulla formazione automatica; la finestra non si riapre da sola nella stessa sessione, la notifica la riapre. Con 2 mancanti si sceglie uno alla volta |

## Area 5 – Mercato: aste e svincolati

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 5.1 | Buste: sessione, offerta, ritiro, chiusura, risoluzione, spareggio | OK | – | – | – | – | 22/11 | il 22/11 sessione, offerte, spareggio e risoluzione di nuovo OK (corsa 22:23) |
| 5.2 | Spareggio che finisce di nuovo in parità | OK | – | – | – | – | 22/11 | vince l'offerta inviata per prima, nessun secondo spareggio, un solo addebito (decisione del 19/11) |
| 5.3 | Waiver in parità | OK | – | – | – | – | 22/11 | vince chi ha inviato per primo; «Spareggio svincolati aperto/annullato», «Svincolato aggiudicato/perso» |
| 5.4 | Live: manuale, sequenziale, rilanci, timer, aggiudicazione | OK | – | – | – | – | 22/11 | 22/11 sera (corsa 22:23): lotto live manuale aggiudicato con un solo addebito, seconda aggiudicazione 400 `market_live_lot_closed`, saldo = somma dei movimenti; nota «Assegnazione da asta a rilanci» (KI-85) giusta, anche nello storico della Rosa a 1280 |
| 5.5 | Live: giro completo `turn_based` | OK | – | – | – | – | 22/11 | fuori turno → 400 `market_live_not_your_turn`; «salta» e «annulla» consumano il turno, come deciso |
| 5.6 | Live: leader senza crediti all'aggiudicazione | OK | – | – | – | – | 22/11 | il lotto va all'offerta successiva valida, o passa; un solo addebito; «Lotto perso: crediti insufficienti» |
| 5.7 | Live: scambio immediato a rosa 35/35 [PREP] | DA FARE | – | – | – | – | – | non si poteva fare il 22/11 né la sera del 23/11 (corsa 22:23): l'asta live non si apre con il turno 11 in corso. Il turno 11 è omologato dall'1:12 del 24/11: da fare prima del blocco del 27/11. Lo scambio a ruolo pieno è OK (5.9) |
| 5.8 | Selettore calciatori dell'asta (buste e live), a schermo | – | OK | OK | OK | – | 22/11 | buste e coda live OK il 21/11; scelta del calciatore da chiamare in un'asta live aperta OK a 1280 il 22/11 sera (corsa 22:23: ricerca, filtri per ruolo, pagine, «Chiama» disattivato senza scelta). Suggerimento: a 1280 la riga dei filtri per ruolo è tagliata a destra |
| 5.9 | Avvisi "Spareggio annullato", busta "non assegnabile", "Scelta richiesta: rosa al completo" visti davvero | OK | – | – | OK | – | 24/11 | API il 22/11 (corsa 22:23). MobB: avvisi e link `/asta` giusti il 23/11; KI-150 corretto (f9ef78d) e riprovato OK il 24/11 (corse 03:03 e 04:13, con le notifiche vere di qa-02 e qa-08): «Spareggio aperto/annullato» sotto «Asta», nessuno sotto «Scambi» |
| 5.10 | Fare un'offerta in busta dall'app [PREP] | – | – | – | – | DA FARE | – | non si poteva fare il 21/11 (mercato fermo per il turno 11) né il 23/11 (M2 NV: dev giù dalle 12:12 alle 12:31 per il piano Railway). Turno 11 omologato il 24/11: serve una sessione a buste aperta in `QA-PREP-PARI` (la apre l'admin `qa-01`) |
| 5.11 | Rimborso del calciatore svincolato con il waiver | APERTO | – | – | – | – | 22/11 | KI-23, da decidere; ancora presente il 22/11 |
| 5.12 | Risoluzione concorrente vera | NV | – | – | – | – | – | regola: una richiesta alla volta per account |
| 5.13 | **Nuova (23/11, 1.3, KI-141).** Valore di mercato nelle offerte: «Valore N» e media, prezzo che parte dal Valore, «hai solo X crediti» | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | OK | 23/11 | EMU OK il 23/11 (M1, asta a buste). Da provare su API, sito e MobB, anche negli svincoli e nel lotto live |

## Area 6 – Formazione

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 6.1 | Moduli, titolari, panchina, validazioni server | OK | – | – | – | – | 12-18/11 |  |
| 6.2 | Bozza: al massimo 11 titolari, 1 portiere e i ruoli del modulo; DELETE solo a turno aperto | OK | – | – | – | – | 22/11 |  |
| 6.3 | Bloccati, indisponibili, fuori rosa | OK | – | – | – | – | 22/11 | bloccati e fuori rosa OK; indisponibili reali NV (nessuno nei dati di dev) |
| 6.4 | Copia formazione precedente | OK | – | – | – | – | 22/11 | non ancora visto il caso di un calciatore uscito dalla rosa dopo la formazione salvata |
| 6.5 | Salvare la formazione a schermo [PREP] | OK | – | OK | OK | OK | 24/11 | W390 il 21/11; MobB il 23/11 (corsa 03:03); EMU flusso 06 dal 21/11, l'ultima il 23/11 (M3 e M4; in M5 NV, turno 11 tutto bloccato). API OK il 24/11 (corsa 00:43): modifiche a calciatori già bloccati rifiutate (400 `athlete_kickoff_locked`, `bench_order_locked`), formazione invariata; modifica dei soli non bloccati NV (nel turno 11 erano tutti bloccati). «Completato» nel selettore del turno OK su sito e MobB (24/11) ed EMU (M4 del 23/11). Resta da decidere `canChangeTurn`: un membro non può scegliere il turno 12 mentre è in corso l'11 |
| 6.6 | Esubero di ruolo in formazione [PREP] | OK | – | – | – | – | 22/11 | `athlete_exceeds_role_quota` con il nome; in tribuna viene tolto senza errore |
| 6.7 | Blocco progressivo, mosse tattiche, formazione automatica al primo blocco [PREP][VIVO] | DA FARE | – | – | – | – | 21/11 | 21/11: blocco progressivo del turno 11 OK in lettura; formazione automatica e margine di blocco ancora da vedere. Prossimo turno vivo: #12, blocco il 27/11 alle 20:30 |
| 6.8 | Formazione dell'operatore [OPER] | OK | – | – | – | – | 21/11 |  |
| 6.9 | Formazione migliore non schiera indisponibili [PREP] | – | DA FARE | DA FARE | DA FARE | – | – | 28/11 (285ac2f): «Applica formazione migliore» e il cambio modulo non mettono titolare chi in campo è grigio (assente nella formazione probabile, anche solo in dubbio; partita rinviata; nessuna partita). Con pochi disponibili per il modulo compare «Formazione migliore non applicata: per il modulo … mancano calciatori disponibili (…)» e la bozza non cambia. Serve un turno con formazioni probabili scaricate e un indisponibile in rosa |
| 6.10 | Alone neutro con legenda quando manca il dato [PREP] | – | DA FARE | DA FARE | DA FARE | – | – | 28/11 (f2396f9): in campo chi non ha dato dalla formazione probabile ha un alone chiaro e la legenda ha la quinta voce «Nessuna informazione»; verde, giallo, rosso e grigio come prima |
| 6.11 | **Nuova (28/11, 1.5).** Contatore dei titolari «0/11» leggibile nel tema scuro e nel chiaro | – | DA FARE | DA FARE | DA FARE | DA FARE | – | Rosario 27/11: sotto gli 11 titolari il numero è bianco nello scuro (blu notte nel chiaro), verde a 11/11. Il sito non ha un contatore dei titolari (cercato nel codice, `apps/web` e `packages/ui`): su W1280 e W390 basta confermarlo a schermo; nell'app (MobB, poi EMU con l'APK 1.5) guardare «0/11» e «10/11» con tema scuro e chiaro. Il 28/11 provato solo nel browser con API finta, non su dev |
| 6.12 | **Nuova (28/11, 1.5).** Ruolo (P, D, C, A) in un cerchio colorato prima del nome, in panchina e in tribuna, anche per gli indisponibili (MobB) | – | DA FARE | DA FARE | DA FARE | DA FARE | – | Rosario 27/11: nell'app la sigla prima del nome, verde P, ambra D, azzurro C, rosso A (come nel «Cambia»), sia nelle righe della panchina sia in quelle della tribuna (toccando «Mostra»), grigie comprese; lo stile delle righe non cambia. Sul sito il Badge del ruolo c'era già anche in tribuna: confermarlo a W1280 e W390. Il 28/11 provato solo nel browser con API finta (24 cerchi: 10 in panchina, 14 in tribuna), non su dev |

## Area 7 – Turni, calendario, classifica

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 7.1 | Calendario pari, partite del turno, soglia partite, reinclusione | OK | – | – | – | – | 12-18/11 |  |
| 7.2 | Calendario dispari dal vivo [PREP] | OK | – | – | – | – | 22/11 | con `QA-PREP-DISPARI`: un riposo per giornata a rotazione, ogni coppia una volta per ciclo |
| 7.3 | Attivazione lega: blocco per crediti | OK | – | – | – | – | 22/11 | blocchi per rose incomplete e calendario mancante OK; un saldo negativo non si raggiunge da nessuna strada dell'API (il blocco per crediti è solo una difesa) |
| 7.4 | Cutoff, ricalcolo, apertura manuale del turno, omologazione, correzioni [OPER] | OK | – | – | – | – | 22/11 | con qa-09. Da decidere: l'operatore può omologare un turno giocato prima che la lega esistesse |
| 7.5 | Notifiche "formazione in scadenza" e "blocco imminente" [PREP][VIVO] | DA RIVERIFICARE | – | – | DA FARE | OK | 21/11 | il 21/11 (corsa 01:53) gli avvisi indicavano il calcio d'inizio invece del blocco e dicevano «della tua formazione»: corretti il 21/11 (KI-101, pilota-1.2). EMU 21/11: testo nuovo OK («4 calciatori della tua rosa si bloccano alle …»). Da rivedere al blocco del 27/11: orario, arrivo prima del blocco, nessun avviso a chi riposa (KI-102) |
| 7.6 | Turni, calendario e classifica a schermo con una lega attiva [PREP] | – | OK | OK | OK | OK | 24/11 | il 21/11 un turno iniziato restava «Prossimo» (KI-101): corretto e riprovato OK (W1280 e W390 il 22/11, MobB il 21/11). «Turno saltato» OK su sito e MobB; EMU 21/11 (M3). Il 24/11 (corsa 04:13) Home lega, Turni e Classifica OK a 360 e 390, e su MobB il motivo del turno saltato (KI-134) |
| 7.7 | Risultati, voti, fantapunti, classifica, scontro diretto | DA FARE | DA FARE | – | – | – | 23/11 | 23/11 (corsa 01:53): provvisori del turno 11 coerenti su API e W1280 (totali = somma dei titolari, nessuna sostituzione prima della fine del turno, scontri 0 gol e pareggio sotto 66, classifica a 0). Il turno 11 è omologato su dev dall'1:12 del 24/11 (dalle 23:01 all'1:02 il fornitore rifiutava le chiamate: quota giornaliera finita): da fare definitivi, sostituzioni automatiche e classifica, anche in `QA-PREP-DISPARI`. Da decidere: «S.V.» con `scoreFinal` già vero quando i voti non sono ancora arrivati |
| 7.8 | **Nuova (23/11, 1.4).** Domande frequenti e Regolamento della lega: «?» del turno saltato con i due motivi, «Partite minime per turno», «Cambi automatici (max)» | OK | OK | OK | DA RIVERIFICARE | DA RIVERIFICARE | 24/11 | 24/11 (corsa 04:13): Domande frequenti via API, nella pagina e nel menù (anche del pannello operatore); un solo «?» accanto a «Stato: Turno saltato» con i due motivi (W1280); nel Regolamento «Partite minime per turno» e «Cambi automatici (max)» (360 e 390). EMU il 23/11 (M4, APK dev della 1.4): Domande frequenti nel menù, «Cambi automatici (max)» e «?» del turno saltato OK; «Partite minime per turno» e la risposta con i due motivi sono arrivati dopo (ee5df14): da rivedere con l'APK 1.4. MobB da provare |
| 7.9 | **Nuova (28/11, 1.5).** Testi in italiano nei turni europei: «Infortunati e squalificati» dello schermo «Partita» e note dei «Cambia» in Formazione (sito e app) [PREP] | – | DA FARE | DA FARE | DA FARE | DA FARE | – | Rosario 27/11: niente «Mid December 2026», «Early January 2027», «Doubtful»; attesi «metà dicembre 2026», «inizio gennaio 2027», «fine febbraio 2027», «Dubbio», «Fuori», «Squalificato». Serve una partita del turno con indisponibili nei dati del fornitore. Il server manda ancora il testo originale: un'app 1.4 li vede in inglese, solo l'APK 1.5 li traduce. Il 28/11 provato nel browser con API finta, non su dev |
| 7.10 | **Nuova (28/11, 1.5).** Pagina dei turni europei a 390 px senza scorrimento orizzontale della pagina e con la barra dei campionati scorrevole | – | DA FARE | DA FARE | – | – | – | Rosario 27/11 (Chrome su Android): a 390 la pagina non deve essere più larga dello schermo (`scrollWidth` = 390), le carte delle partite («Borussia Mönchengladbach», «IN PROGRAMMA») stanno dentro e la barra dei campionati (Bundesliga, Serie A, Ligue 1, La Liga…) si sposta col dito; a 1280 invariato. Il 28/11 provato con Chromium e API finta (5 campionati), non su dev |
| 7.11 | **Nuova (28/11).** Gol o assist annullato (VAR, fuorigioco) non dà bonus e i punti si ricalcolano | DA FARE | – | DA FARE | DA FARE | – | – | Rosario 27/11: Venezia–Bologna 0–0 (turno 12), gol annullato al 15'; A. Hainaut aveva ancora l'icona dell'assist. Dopo la pubblicazione: API (voti della partita e dello scontro diretto) senza `assist`/`goal` nei bonus di chi aveva il gol annullato, fantapunti scesi dello stesso valore, totale della squadra e scontro ricalcolati; a schermo (W390 e MobB, «Scontro diretto» e dettaglio partita) niente icona del gol/assist annullato, il resto (giallo, voto) invariato. Un gol vero resta. Si ripara da solo solo entro 72 ore dalla fine della partita e a turno non omologato (riga del 28/11 di `known_issues.md`). Il 28/11 provato solo con test automatici |

## Area 8 – Notifiche

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 8.1 | Centro notifiche: elenco, segna letta, badge | OK | OK | – | – | – | 22/11 | 22/11: notifica altrui → 404, id non valido → 422; pallino uguale all'API |
| 8.2 | "Segna tutte lette" e `limit` | OK | OK | – | – | – | 22/11 | `limit` non esiste: l'API usa `page` e `pageSize` (valori fuori scala → 422); pagine senza doppioni né buchi |
| 8.3 | Generate da invito, scambio e asta | OK | – | – | – | – | 22/11 | 22/11: inviti (ricevuto, accettato, rifiutato, revocato), nuovo partecipante, lega al completo, aste e svincolati. Avvisi di scambio: ultimi visti prima del 18/11 (mercato fermo) |
| 8.4 | Link profondo sul web | OK | OK | – | – | – | 22/11 |  |
| 8.5 | Tocco su una notifica di scambio nell'app → Mercato › Scambi | – | – | – | – | OK | 18/11 |  |
| 8.6 | Tocco su ogni altro tipo di notifica (asta, turno, invito, fantallenatori, operatore) | – | OK | – | OK | OK | 22/11 | MobB OK il 21 e 22/11 (18 tipi, poi 7 con la lega giusta). W1280 22/11. EMU: scambio, lega partita, turno aperto, nuovo invito, «Carica altre» (18/11), blocco formazione (21/11); il 22/11 (M4) asta («Sei stato sorpassato» apre Mercato › Asta › Live), operatore (apre il Profilo) e lega eliminata (8.7) |
| 8.7 | Notifica di una lega eliminata: apre Scambi senza lega | – | OK | – | OK | OK | 23/11 | KI-12: corretto il 21/11 (pilota-1.2). «Lega eliminata» ha link `/` e apre la Home di una lega esistente senza errori: sito il 22/11, EMU il 22/11 (M4), MobB il 23/11 (corsa 03:03) |
| 8.8 | Push ed email reali | – | – | – | – | NV | – | l'emulatore non ha Play Store, quindi niente push (confermato il 21/11: `pushCount 0`): da vedere su un telefono vero |
| 8.9 | **Nuova (21/11, KI-12).** Tocco su una notifica di un'altra lega: l'app passa a quella lega | – | OK | – | OK | OK | 22/11 | EMU 21/11 (M4: con `QA-PREP-PARI` attiva, «Blocco formazione in arrivo «QA-PREP-DISPARI»» apre Formazione e cambia lega); MobB 22/11 (7 tipi); W1280 22/11 (lega giusta nel selettore). Con la push: NV (8.8) |

## Area 9 – Web

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 9.1 | Pagine principali senza errori in console e senza scorrimento orizzontale | – | OK | OK | – | – | 22/11 |  |
| 9.2 | Tab Mercato a 390 | – | – | OK | – | – | 22/11 |  |
| 9.3 | Contrasti del tema chiaro e scuro | – | DA RIVERIFICARE | DA RIVERIFICARE | – | – | 24/11 | tribuna e ambra «attenzione» (KI-98, KI-99) e nomi «senza voto» e «s.v.» delle sfide (KI-120, 5,38:1) OK il 21-24/11. KI-151 corretto (bdd4ffc): il 24/11 (corse 03:03 e 04:13) sul campo «s.v.» ha il gradiente viola e «definitivo» è bianco con testo scuro, a 1280 e 390, in tema chiaro e scuro. Resta «provvisorio» [VIVO]: compare solo con una partita in corso, da vedere dopo il blocco del 27/11; da decidere il contrasto del suo blu (3,68:1 sul secondo colore del gradiente, visto solo con una pastiglia finta) |
| 9.4 | Pagine nuove: "+ Tester" con liste impaginate, "Elimina" lega, "Rimetti nel turno" ("+ Tester" ed "Elimina" sono [OPER]) | – | OK | OK | – | – | 23/11 | «+ Tester» ed «Elimina» OK il 21/11 (impaginazione dei tester NV: solo 3 tester). «Rimetti nel turno» senza calendario diceva «Il ricalcolo non è riuscito»: corretto il 21/11 (KI-101), OK a 1280 il 22/11 e a 390 il 23/11 (corsa 03:03: «Escludi» e «Rimetti nel turno» 200 con i loro messaggi) |
| 9.5 | Pagine principali con una lega attiva e rose piene [PREP] | – | OK | OK | – | – | 24/11 | 16 pagine OK il 21-22/11. P4 del 22/11 (Amministrazione di una lega attiva con «Prima salva la configurazione…» e «Invitati» disattivata) corretto (KI-122) e riprovato OK a 1280 e 390 il 23/11 (corse 03:03 e 04:13, 15 pagine senza errori) e il 24/11 (corsa 04:13) |

## Area 10 – App mobile (browser ed emulatore)

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 10.1 | Schermate principali senza errori | – | – | – | OK | OK | 24/11 | MobB OK dal 21/11 (Svincolati nascosta per scelta). KI-149 corretto (cd68390) e riprovato OK il 24/11 (corse 03:03 e 04:13): un membro che apre Fantallenatori vede «Permessi insufficienti» senza richieste di amministrazione né 403; giro di 11 schermate senza errori. EMU flusso 02 dal 21/11, l'ultima il 23/11 (M3, M4 e M5) |
| 10.2 | Schermate principali con contenuti di lega [PREP] | – | – | – | OK | OK | 24/11 | EMU 21/11 (M3). KI-123 corretto nella 1.4: MobB OK il 24/11 (corse 03:03 e 04:13: «Campionati 3», un campionato per riga, senza tagli); EMU OK il 23/11 (M4, APK dev della 1.4). Flusso 05 OK il 23/11 in M3 e M5, instabile in M4 (passa al secondo tentativo) |
| 10.3 | Pannello operatore mobile [OPER] | – | – | – | OK | OK | 23/11 | MobB 21/11 con qa-09 (notifiche operatore NV: nessuna). EMU OK il 23/11 con qa-09: «Elimina» lega con conferma (M1, vedi 2.8); Riepilogo, Versione app e Dettaglio del Valore (M4, APK dev della 1.4) |
| 10.4 | Coerenza con il web: etichette, stati scambi, colori ruolo, causali crediti | – | – | – | OK | – | 22/11 | MobB contro W390 il 21 e 22/11; colori di ruolo della stessa tinta ma di tonalità diverse (suggerimento) |
| 10.5 | Schermata di accesso: tema chiaro, bandiera Premier, tastiera, titolo | – | – | – | – | OK | 18/11 | anche «GIOCA» leggibile |
| 10.6 | Galleria e fotocamera per l'avatar | – | – | – | – | OK | 23/11 | galleria OK il 18/11 e il 23/11 (M1, vedi 1.6). Voce chiusa «solo galleria»: l'app non offre la fotocamera e non serve (decisione di Rosario del 23/11, KI-158) |
| 10.7 | Push vere, Google nativo | – | – | – | – | NV | – | serve un telefono vero (l'emulatore non ha Play Store) |
| 10.8 | **Nuova (21/11, KI-111).** Avviso di nuova versione dell'app | OK | OK | – | – | OK | 24/11 | EMU 21/11 (M5): avviso con «Scarica» e «Più tardi» (che non lo ripropone); «Versione app» dell'operatore OK il 23/11 (M4). API: qa-08 riceve 403 su `/admin/app-version`, lettura OK il 22/11. W1280 OK il 23/11 con qa-09 (corsa 03:03) e il 24/11 (corsa 04:13, a 1280 e 390: elenco delle versioni e conferma prima di salvare; la conferma dice «Annunciare la versione X…?», non «Sei sicuro?»: formulazione da decidere). Su dev il link è di prova (`example.com`) |
| 10.9 | **Nuova (21/11, KI-114).** «Segnala un problema»: pagina giusta e versione dell'app | OK | OK | – | – | OK | 23/11 | EMU 21/11 (APK `04cc83b`): dalla Rosa `Roster` e `1.2.0 (3)`, da una notifica `Formation`; la strada Home lega › Rosa NV (pulsante assente). API OK il 22/11. W1280 OK il 23/11 con qa-09 (corsa 03:03: pagina e versione visibili nelle segnalazioni). Restano su dev segnalazioni di prova da chiudere a mano |
| 10.11 | **Nuova (25/11, 1.5).** Sostituto dopo uno scambio sbilanciato nell'app [PREP] | – | – | – | DA RIVERIFICARE | NV | 25/11 | **DA RIVERIFICARE con i 3 avvisi nuovi della sera del 25/11** (come 4.13): avviso dei crediti che non bastano sotto il riquadro arancione e riquadro «Nessun libero alla tua portata…» nel foglio dei sostituti; foglio della controproposta «Inviare la controproposta?» / «Invia controproposta»; ruoli sotto quota a rosa 35/35 (riga nel riquadro giallo, anche su «Accetta» di un 1 per 1, che passa dal foglio con «Accetta scambio»; riquadro «Ruoli sotto quota…» in Rosa; testo nell'avviso dopo l'ultimo sostituto). Il flusso Maestro 07 conferma il foglio se compare. Poi, come 4.13, nell'app: foglio dal basso con il riquadro arancione e «Accetta e scegli» (anche per chi propone o controproponga e per l'admin che approva), foglio «Scegli il sostituto» con «Più tardi» e il tasto indietro che chiudono, conferma con il conto, riquadri in Rosa e Formazione; la notifica apre Rosa con la scelta (`/rosa?sostituto=1`). Una volta per sessione: con «Più tardi» non si riapre da sola fino al riavvio. EMU NV fino all'APK 1.5 |
| 10.10 | **Nuova (23/11, KI-143 e KI-155).** Correzioni dell'app nella 1.4: Asta senza leghe, «Salva regolamento» con conferma, indietro dopo «Elimina lega», Profilo fermo su «Aspetto» dopo il cambio tema | – | – | – | APERTO | OK | 24/11 | EMU OK il 23/11 (M4, APK dev della 1.4): «Nessuna lega», «Regolamento salvato» visibile, indietro che non torna sulla lega eliminata, Profilo che resta su «Aspetto». MobB il 24/11 (corsa 04:13): «Salva regolamento» e indietro OK, «Impostazioni notifiche» per il lettore di schermo OK (KI-144), «Nessuna lega» NV (nessun account senza leghe). APERTO solo su MobB: dopo il cambio tema il Profilo torna in cima (la correzione 377b0a3 non tiene nell'app aperta nel browser); non ancora in `known_issues.md` |

## Area 11 – Salute e prestazioni

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 11.1 | `/live`, `/ready`, letture sotto 2 s, nessun 5xx | OK | – | – | – | – | 24/11 | 24/11 (corse 03:03 e 04:13): `/live` e `/ready` 200, letture al massimo circa 1 s, nessun 5xx. Scritture lente: conferma dell'import CSV 6-8,3 s per 105-140 righe, regolamento 5 s, sincronizza 9,5 s, riempimento 6 s |
| 11.2 | Tempi su una lega attiva con rose piene [PREP] | OK | – | – | – | – | 22/11 | letture al massimo 0,77 s, nessun dato altrui esposto |
| 11.3 | `/realtime/stream` | OK | – | – | – | – | 22/11 | si apre, riceve un evento in circa 1 s, 401 senza token |
| 11.4 | **Nuova (28/11).** Job/Operatore: il giro delle formazioni probabili parte da solo e il Prossimo giro è corretto [OPER] | DA FARE | DA FARE | – | – | – | – | riga del 28/11 «Giro delle formazioni probabili che non parte (crontab 07:00 UTC)» di `known_issues.md`. Operatore › Job: «Formazioni probabili» acceso con frequenza 1 ora; «Ultima partenza» al massimo un'ora fa e «Prossimo giro» = ultima partenza + 1 ora (mai «Mai eseguito» né un orario passato di ore); il giorno dopo, entro le 08:00 UTC, le partite dei prossimi 4 giorni hanno una formazione probabile letta dopo le 07:00 (schermo «Partita» o diagnosi dell'operatore). Il 28/11 provato solo con test automatici |

## Area 12 – App Android: azioni sull'app (solo EMU)
Le aree 1-8 sono state provate quasi sempre via API. Qui ci sono le stesse funzioni fatte **dall'app**, più le cose che esistono solo su un telefono. Quando serve l'altra parte (per esempio chi riceve uno scambio), quella si fa via API con un altro account QA.

| Cod | Voce | EMU | Blocco | Ultima | Note |
|---|---|---|---|---|---|
| 12.1 | Registrazione dall'app con un account usa e getta, messaggio di verifica | OK | M1 | 21/11 | nessun messaggio di verifica: su dev la conferma dell'email è spenta per scelta (KI-73) |
| 12.2 | "Password dimenticata" dall'app | OK | M1 | 21/11 | compare «Controlla la tua email» |
| 12.3 | Profilo: nome, nickname, preferenze notifiche, ore di silenzio, tema chiaro e scuro | OK | M1 | 23/11 | 21/11: nome salvato e tema scuro subito su tutto (KO-1, KI-70). Voce chiusa OK il 23/11 (M1): tema chiaro e scuro applicati subito; il Profilo resta su «Aspetto» dopo il cambio (M4, vedi 10.10) |
| 12.4 | Esportazione dati ed eliminazione account dall'app (account usa e getta) | OK | M1 | 21/11 | eliminazione OK; l'esportazione nell'app non c'è per scelta (KI-71: la copia dei dati si chiede a info@fantappero.it) |
| 12.5 | Sessione: app in background per più di 30 minuti e ritorno (rinnovo del token), poi riavvio | OK | M1 | 21/11 | 52 minuti in background, poi riavvio: sempre collegata. Al ritorno mostrava la home di una lega già eliminata finché non si navigava |
| 12.6 | Creare una lega dall'app (nome, competizioni, regole) | OK | M1 | 21/11 |  |
| 12.7 | Ingresso con codice; invito nominale ricevuto, accettato e rifiutato | OK | M1 | 23/11 | OK il 21/11; «Annulla invito» dall'app dell'admin OK il 23/11 (M1, KI-68) |
| 12.8 | Partecipanti, directory fantallenatori, cambio della lega attiva [PREP] | OK | M1 | 23/11 | anche l'email dei fantallenatori visibile solo all'admin (KI-92); il 23/11 (M4, APK dev della 1.4) una lega creata via API compare nel selettore tirando per aggiornare |
| 12.9 | Listone: filtro ruolo, ricerca, "Solo disponibili" [PREP] | OK | M2 | 22/11 | ricerca e filtro ruolo OK il 21/11; «Solo disponibili» OK il 22/11 (M3) |
| 12.10 | Admin dall'app: assegnazione manuale di uno slot, svincolo con rimborso [PREP] | DA FARE | M2 | 21/11 | assegnazione OK il 21/11; manca lo svincolo con rimborso (il 23/11 M2 NV: dev giù dalle 12:12 alle 12:31 per il piano Railway) |
| 12.11 | Scambi dall'app: proponi, accetta, rifiuta, annulla, controproposta [PREP] | DA FARE | M2 | – | il 21/11 mercato fermo per il turno 11, il 23/11 M2 NV (dev giù per il piano Railway); si può fare dal 24/11 (turno 11 omologato). Provare anche la conferma «Accetta scambio» (KI-80) e «Nuova proposta» che resta aperta con l'errore (KI-99) |
| 12.12 | Approvazione admin di uno scambio dall'app [PREP] | DA FARE | M2 | – | mercato fermo il 21/11, M2 NV il 23/11 (fermo di Railway) |
| 12.13 | Asta a buste dall'app: offerta, ritiro, esito [PREP] | DA FARE | M2 | – | mercato fermo il 21/11, M2 NV il 23/11 (fermo di Railway); controllare anche gli orari in ora italiana (KI-78) |
| 12.14 | Asta live dall'app: rilancio, timer, aggiudicazione (gli altri rilanciano via API) [PREP] | DA FARE | M2 | – | mercato fermo il 21/11, M2 NV il 23/11 (fermo di Railway) |
| 12.15 | Movimenti crediti e causali [PREP] | OK | M2 | 21/11 | «Aggiustamento admin», «Assegnazione …», «Acquisto rosa» con data e saldo |
| 12.16 | Formazione: modulo, titolari, panchina e ordine, bozza, copia della precedente [PREP] | OK | M3 | 23/11 | 21/11 a turno in corso: modulo, titolari, panchina, «Bozza», «Salva» e «Svuota formazione» OK; 22/11 (M3): cambio modulo che tiene i titolari (KI-77), copia della precedente, esubero in tribuna (KI-84), «Sistema la panchina», «Svuota» e «Ripristina» OK; 23/11 (M4, APK dev della 1.4): «Completato» per i turni giocati, il turno scelto resta, «?» del blocco |
| 12.17 | Calciatori bloccati o indisponibili visibili ma non selezionabili [PREP] | OK | M3 | 21/11 | lucchetto e niente «Cambia», in campo e in panchina |
| 12.18 | Turni europei, calendario, scontro diretto, classifica [PREP] | OK | M3 | 23/11 | «In corso» OK il 21/11; «Turno saltato» il 22/11 (M3, KI-102); il 23/11 (M4, APK dev della 1.4) anche il motivo del turno saltato e il «?» (KI-134 corretto) |
| 12.19 | Centro notifiche: badge, segna letta, segna tutte lette | OK | M4 | 22/11 | badge «9+», non lette e segna letta al tocco OK il 21/11; l'avviso «Novità» dell'operatore arriva, anche programmato; «Segna tutte lette» OK il 22/11 (M4: da 18 a 0) |
| 12.20 | Preferenze notifiche e ore di silenzio rispettate | OK | M4 | 22/11 | preferenze rispettate il 22/11 (M4). Ore di silenzio NV: valgono solo per email e push, che sull'emulatore non arrivano (8.8) |
| 12.21 | Tasto "indietro" di Android su ogni schermata: non esce dall'app per sbaglio e non perde i dati inseriti | OK | M5 | 22/11 | tasto indietro OK il 22/11 (M5); non provata la perdita dei dati inseriti in un modulo |
| 12.22 | Accessibilità: testo grande (scala 1,3) e TalkBack sui pulsanti principali | OK | M5 | 22/11 | testo grande (scala 1,3) OK il 22/11 (M5); TalkBack NV sull'emulatore |
| 12.23 | Rete assente o lenta (modalità aereo): messaggi d'errore e ripresa | OK | M5 | 23/11 | 22/11 (M5) KO parziale (KI-142): avviata senza rete restava sull'accesso senza messaggio. Corretto nella 1.4 e OK il 23/11 (M4 e M5, APK dev della 1.4): «Connessione non disponibile» e «Riprova», poi rientro senza password quando la rete torna; con l'app già aperta «Ricarica» funziona |
| 12.24 | Tema chiaro e scuro su tutte le schermate principali | OK | M5 | 22/11 | Profilo in tema scuro il 21/11; tutte le schermate principali leggibili in tema scuro il 22/11 (M5) |
| 12.25 | Schermo più piccolo: l'AVD `maestro_e2e` (Pixel 5) | OK | M5 | 21/11 | tutte le prove del 21/11 su questo AVD, senza problemi di impaginazione |

## Area 13 – Allineamento app ↔ sito e conferme (release 1.5)

Nuova il 28/11 (riga «Fatto: allineamento app↔sito, conferme e foglio sostituto doppio (1.5)» di `known_issues.md`). Tutto **DA FARE** perché fatto solo sul ramo del worktree, con i test di logica e prove su react-native-web, ma non ancora provato a schermo né pubblicato. Le conferme dell'app sono finestre dell'app (`ConfirmDialog`), non `Alert.alert`: **su MobB si aprono e si possono provare**, a differenza di «Elimina lega» (2.8). Il sito è il riferimento: l'app deve dire le stesse parole. Con MobB si provano anche i testi (stessa frase del sito); sul sito le conferme nuove sono la 13.2 e la 13.3 (W1280 e W390).

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 13.1 | **Nuova (28/11, 1.5).** App, Amministrazione lega › calendario: «Genera calendario» e «Conferma calendario» aprono «Vuoi generare/confermare il calendario?» (con «Annulla»); con una rosa non in regola l'avviso con squadre e problemi e «Genera comunque» / «Conferma comunque» [PREP] | – | – | – | DA RIVERIFICARE | DA RIVERIFICARE | – | **DA RIVERIFICARE (28/11, D2):** «Vai a Partecipanti» (compare dopo «Genera comunque» con l'errore «Completa le rose…») con la configurazione mai salvata apre «Configurazione» (non più la scheda «Invitati», che è disattivata) e porta la pagina fino a «Prossime fasi»; con la configurazione salvata apre «Invitati» e scorre allo stesso punto; poi si può tornare da una scheda all'altra (prima da «Configurazione» non si tornava più a «Invitati»). prova con le rose in regola (conferma normale, nessun avviso), con un esubero di ruolo (avviso, «comunque» genera) e con una rosa con slot vuoti o meno di 3 campionati (nome della squadra nella riga «non potrà schierare la formazione»); «Annulla» non chiama `…/calendario/genera`; dopo il successo «Calendario generato: N incontri su M giornate.»; con l'errore «Completa le rose…» compare «Vai a Partecipanti». Stessi testi del sito (provarli a confronto a W390) |
| 13.2 | **Nuova (28/11, 1.5).** «Rimuovi» un partecipante chiede «Sei sicuro?» con il nome, su sito e app [PREP] | – | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | – | **DA RIVERIFICARE (28/11, D1):** il testo della conferma e dell'esito dice «allineato agli iscritti» solo se i previsti cambiano davvero (restano almeno 4 iscritti e i previsti sono più degli iscritti): «Il numero dei partecipanti previsti si allinea agli iscritti rimasti.» / «…è stato allineato agli iscritti (N).»; altrimenti «I partecipanti previsti restano N.». Prova su sito (W1280, W390) e app (MobB): 4 previsti e 3 iscritti → «Rimuovi» → «Iscritti 2 / Previsti 4» e «I partecipanti previsti restano 4.»; 8 previsti e 6 iscritti → «Previsti» scende a 5 e il messaggio lo dice. Sito e app devono dire le stesse parole. lega in bozza, un membro di prova: «Rimuovi» apre «Vuoi rimuovere NOME dalla lega?…» con «Annulla» e «Rimuovi»; «Annulla» lascia il membro; «Rimuovi» lo toglie e il conto «Iscritti» scende; l'admin non ha «Rimuovi»; a stagione avviata «Rimuovi» non c'è |
| 13.3 | **Nuova (28/11, 1.5).** Operatore › Notifiche: «Invia a N utenti» chiede «Sei sicuro?» con i destinatari e i canali, su sito e app; «Invia a me come prova» no [OPER] | – | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | DA RIVERIFICARE | – | **DA RIVERIFICARE (28/11, D3):** con un solo destinatario il testo è al singolare: «Invia a 1 utente», «Inviata a 1 utente (0 con push).», «Programmata per 1 utente.», «Destinatari» «1 utente», «1 utente selezionato» anche nella scheda Prove; «Tutti i N utenti» e il conteggio degli utenti restano come prima. Nello Storico le etichette già salvate restano com'erano («1 utenti scelti»); solo i nuovi invii dicono «1 utente scelto». «Stai per inviare la notifica «TITOLO» a N utenti. Canali: App + push. Dopo l'invio non si può annullare.»; con «Tutti gli utenti» il testo dice «a tutti gli utenti»; programmata: «Programma» e «per N utenti»; «Annulla» non crea nulla (nessun elemento nello Storico); senza titolo o senza destinatari l'errore compare e la finestra no. **Prova solo a se stessi** (un utente di prova), non a tutti gli utenti reali |
| 13.4 | **Nuova (28/11, 1.5).** App, Operatore › Email: «Invia a N utenti» chiede «Sei sicuro?» [OPER] | – | – | – | DA RIVERIFICARE | DA RIVERIFICARE | – | **DA RIVERIFICARE (28/11, D3):** con un solo destinatario «Invia a 1 utente», «Inviare l'email a 1 utente?» (sul sito il `window.confirm` dice la stessa frase) e «Email inviata a 1 utente.», «Destinatari» «1 utente»; con più utenti restano «N utenti». «Inviare l'email a N utenti? Dopo l'invio non si può annullare.»; «Annulla» non invia; «Invia a me come prova» parte senza finestra. Il sito resta con il suo `window.confirm`. Provare l'invio solo a un utente di prova |
| 13.5 | **Nuova (28/11, 1.5).** App, Operatore › Listone: «Aggiorna listone dal provider» apre la scelta (non parte da solo) e si può annullare [OPER] | – | – | – | DA FARE | DA FARE | – | prova la finestra: due opzioni («Aggiungi i nuovi calciatori…» predefinita e «Aggiorna anche i ruoli dal fornitore» con l'avviso «possono andare fuori quota»), «Annulla» chiude senza chiamare `…/listone/aggiorna`. **Non avviare l'aggiornamento vero** (chiama il fornitore dati e consuma quota) senza il permesso di Rosario; con il suo permesso, con l'opzione dei ruoli compare l'anteprima («Conferma i nuovi ruoli» / «Annulla: i ruoli restano come sono») |
| 13.6 | **Nuova (28/11, 1.5).** App, Operatore › Listone: «Ripristina i ruoli cambiati da un aggiornamento» [OPER] | – | – | – | DA FARE | DA FARE | – | stesso blocco del sito (in fondo, dopo «Valore»): data e ora di Roma (predefinita 21/11 12:00), «Mostra cosa cambia» (anteprima senza modificare nulla), «Ripristina» → «Sì, ripristina» / «Annulla». Provare solo l'anteprima; il ripristino modifica i ruoli |
| 13.7 | **Nuova (28/11, 1.5).** App, pannello operatore: tasto «Indietro» ben visibile in ogni schermata [OPER] | – | – | – | DA FARE | DA FARE | – | in cima a Leghe, Utenti, Listone, Turni, Job, Notifiche, Email, Segnalazioni e Versione app: torna alla schermata prima o al Riepilogo; dal Riepilogo esce dal pannello e torna all'app. Anche a 360 px, senza coprire il titolo |
| 13.8 | **Nuova (28/11, 1.5).** App, Operatore › Job: riepilogo «Attivi» e «Prossimo giro»; Listone: stesso ordine dei blocchi del sito [OPER] | – | – | – | DA FARE | DA FARE | – | Job: «Attivi N / M» con «K spenti» e «Prossimo giro» con il tempo e il titolo, uguali al sito (W390); Listone: prima il listone, poi (dopo l'aggiornamento con i ruoli) l'anteprima, poi «Storico stagioni», «Valore» e «Ripristina i ruoli» |
| 13.9 | **Nuova (28/11, 1.5).** App, asta live: «Offerta personalizzata» [PREP] | – | – | – | DA FARE | DA FARE | – | con un lotto aperto: scrivere un importo sopra il minimo → «Rilancia a N» rilancia quell'importo e svuota il campo; campo vuoto → «Rilancia a <minimo>»; sotto il minimo il server rifiuta con il suo errore; a mercato non attivo il campo è disattivato. Come il sito |
| 13.10 | **Nuova (28/11, 1.5).** App, Amministrazione lega › Invitati: elenco partecipanti con avatar, email, «· IA», nome che apre il profilo (non il proprio) e «Assegna rosa random» per i membri IA [PREP] | – | – | – | DA FARE | DA FARE | – | il tocco sul nome apre il profilo del fantallenatore (`CoachProfile`) con la lega; il proprio nome non è un tasto; «Assegna rosa random» solo per i membri IA (e solo prima dell'avvio): «Rosa random assegnata a NOME: 25/25 giocatori.»; dopo «Rimuovi» il messaggio «NOME è stato rimosso dalla lega.» seguito da «I partecipanti previsti restano N.» o, solo se i previsti cambiano davvero, «Il numero partecipanti previsti è stato allineato agli iscritti (N).» (vedi 13.2) |
| 13.11 | **Nuova (28/11, 1.5).** App, Directory fantallenatori: filtro «Tipologia» (Tutte, Manuale, IA) e «Reimposta filtri» | – | – | – | DA FARE | DA FARE | – | IA mostra solo le IA, Manuale solo le persone; «Reimposta filtri» compare con un filtro attivo (ricerca, tipologia o «Solo disponibili») e li azzera tutti; contatore e pagine seguono il filtro. Come il sito (W390) |
| 13.12 | **Nuova (28/11, 1.5).** App: «Scegli il sostituto» si apre una volta sola con la notifica «Scegli il sostituto» di un'altra lega [PREP] | – | – | – | DA FARE | DA FARE | – | lega A attiva, utente con un sostituto da scegliere in lega B (dopo uno scambio sbilanciato, vedi 4.12/10.11): toccare la notifica nell'elenco o la push → passa alla lega B, apre Rosa e il foglio **una volta**; «Più tardi» lo chiude e non riappare da solo (neanche dopo qualche secondo); il riquadro «Rosa incompleta» e «Scegli il sostituto» riaprono il foglio a richiesta; un secondo tocco sulla notifica, dopo un po', lo riapre |

## Scaletta

### Notte (corse cloud, dalle 22:23 alle 04:13)
Ogni corsa prova, nelle sue aree e nella colonna della sua piattaforma, prima le voci DA FARE senza prerequisiti mancanti, poi le DA RIVERIFICARE. Se le restano risorse, ripassa quelle con il prerequisito appena pronto. L'app nel browser (MobB) e la coerenza con il web a 390 px (10.4) restano alla corsa delle 03:03.

**Gruppi A, B e C a notti alterne** (decisioni di Rosario del 22/11 e del 24/11, fino al 27/11):
- il Gruppo A (23:33) parte solo nei giorni dispari del mese;
- il Gruppo B (00:43) parte solo nei giorni pari del mese, cioè nella stessa notte del Gruppo A;
- il Gruppo C (01:53) parte solo nei giorni dispari del mese, cioè nelle notti che cominciano in un giorno pari;
- quindi la notte 24→25/11 fa solo C (alle 01:53 del 25), la notte 25→26/11 A e B (alle 23:33 del 25 e alle 00:43 del 26), la notte 26→27/11 solo C, la notte 27→28/11 A e B.

| Corsa | Quando | Aree | Voci per le prossime notti |
|---|---|---|---|
| 22:23 Mercato | ogni notte | 4, 5 | 4.7 e 5.7 [PREP] ora che il turno 11 di `QA-PREP-PARI` è omologato, prima del blocco del 27/11; 5.13 (Valore nelle offerte, 1.3) su API, W1280 e W390; 4.12 fatta il 25/11 (OK); 4.13 (W1280, W390) da riverificare con i 3 avvisi nuovi della sera del 25/11 (crediti, controproposta, ruoli sotto quota) appena pubblicati su dev; dopo il blocco del 27/11 il rifiuto a turno in corso della 4.12. Corsa sospesa dal 25/11 (riattivarla verso l'1/12) |
| 23:33 Gruppo A | giorni dispari | 1, 2 | 2.3 a W1280 e W390 appena pubblicata la correzione KI-165 (plurale degli iscritti e conto degli inviti); nelle aree 1 e 2 non resta altro sulle piattaforme cloud |
| 00:43 Gruppo B | giorni pari | 3, 6 | 3.15 (media, Valore e carriera, 1.3) su API, W1280 e W390; 6.7 [VIVO] dopo il blocco del 27/11 (alle 00:43 del 28/11) |
| 01:53 Gruppo C | giorni dispari (notti che iniziano in un giorno pari) | 7, 8 | 7.7 (API, W1280) ora che il turno 11 è omologato: definitivi, sostituzioni automatiche e classifica; 7.5 alla prima corsa dopo il blocco del 27/11: orario, arrivo prima del blocco, nessun avviso a chi riposa |
| 03:03 Gruppo D | ogni notte | 9, 10, 11 e MobB di tutte le aree | su MobB 3.15, 5.13 e 7.8 (funzioni della 1.3 e della 1.4) e 2.3 appena pubblicata la correzione KI-165; appena la 1.5 è su dev 10.11 su MobB (sostituto dopo uno scambio sbilanciato, con i 3 avvisi nuovi della sera del 25/11, fuori dal turno in corso); dopo il blocco del 27/11 9.3 «provvisorio» (W1280, W390) e 7.5 su MobB |
| 04:13 Verifica | ogni notte | tutte | regressioni: le voci «CORRETTI/Risolto/Fatto» degli ultimi 3 giorni di `known_issues.md` e, appena pubblicata, la correzione KI-165; il Profilo che torna in cima su MobB (10.10) è già APERTO |

### Mobile di giorno: emulatore Android sul PC di Rosario
I blocchi M1-M5 li fa la sessione **«rosario-quirky-marble»** aperta sul PC di Rosario, con l'app sull'emulatore (AVD `maestro_e2e`), Maestro e `adb`, contro l'API di dev. Li avvia da sola con i timer della sessione e scrive il rapporto nella sua chat.
- **Riserva:** le attività pianificate di Windows `\FantAppero\` (script `C:\Users\trott\fantappero-qa\corsa-mobile.ps1`), una al giorno per blocco.
  - Ogni partenza scrive il segnaposto `C:\Users\trott\fantappero-qa\markers\<data>-<blocco>.started`. Se c'è già, o se Maestro ha girato nell'ultima ora, l'altra partenza salta: un blocco non si fa due volte. Alle 12:27, 18:27 e 21:27 la riserva parte prima del timer della sessione; chi parte per primo fa il blocco.
  - I rapporti delle attività di Windows vanno in `C:\Users\trott\fantappero-qa\log\` (`<data>-<blocco>.md`).
  - Partono solo con Rosario collegato al PC. Per spegnerle: `Disable-ScheduledTask -TaskPath '\FantAppero\' -TaskName *`.
- **Regole per tutti i blocchi:**
  - account `qa-02` (`qa-03` per gli scambi, `qa-09` per le voci [OPER]), lega `QA-PREP-PARI`;
  - prima di ogni blocco `git pull` su `main`; solo dev, mai pilota;
  - si provano solo le voci del blocco ancora DA FARE o DA RIVERIFICARE nella colonna EMU.
- **Build:** se `main` ha modifiche in `apps/mobile` o `packages`, si ricompila l'APK dev prima del blocco, solo a emulatore spento (insieme non stanno nei 16 GB di RAM) e senza altre build in corso sul PC.
- **Se il PC è spento** o la sessione non è aperta, il blocco salta e lo recupera quello successivo.

| Blocco | Timer della sessione | Riserva Windows | Voci del registro |
|---|---|---|---|
| M1 Accesso, account e leghe | 09:37 | 09:57 | il 23/11 fatte tutte (1.6, 2.7, 2.8, 10.3, 10.6, 12.3, «Annulla invito»); resta 2.3 sull'APK con la correzione KI-165, poi solo il ripasso dei flussi Maestro |
| M2 Rosa e mercato | 12:37 | 12:27 | 12.10 (svincolo con rimborso); a mercato aperto (turno 11 omologato il 24/11) 5.10 e 12.11-12.14. Il 23/11 tutto NV per il fermo di Railway (12:12-12:31) |
| M3 Formazione e turni | 15:25 | 15:27 | 7.8 sull'APK 1.4 («Partite minime per turno» e la nuova risposta del «?»); poi il ripasso dei flussi Maestro (il 23/11: 01-06 OK, 07 e 08 NV) |
| M4 Notifiche | 18:37 | 18:27 | nessuna voce DA FARE: solo il ripasso dei flussi Maestro (il 23/11, con l'APK dev della 1.4, anche le 10 verifiche della 1.4 OK; flussi 01-04 e 06 OK, 05 instabile, 07 e 08 NV) |
| M5 Sistema e ripasso | 21:37 | 21:27 | tutti i flussi Maestro di `apps/mobile/e2e/maestro/flows/dev/` sull'ultimo APK (il 23/11: da 01 a 05 OK; 06 NV con il turno 11 tutto bloccato; 07 solo a mercato aperto; 08 va lanciato con `NOTIF_ID`). Il 05 usa la sessione aperta dal 01: lanciare il 04 per ultimo (KI-162). 12.23 OK il 23/11 |

Ogni blocco dura al massimo un'ora circa: le voci che non riesce a fare passano al giorno dopo, finché nel registro non restano voci DA FARE per quel blocco. Quando un blocco non ha più voci DA FARE, fa solo il ripasso dei flussi Maestro.

Restano NV sul mobile le push vere e l'accesso con Google (8.8, 10.7): l'emulatore non ha Play Store, serve un telefono vero.

### Prossimi appuntamenti
- **Dal 24/11** (turno 11 omologato all'1:12): 7.7 (definitivi e classifica del turno 11), 4.7, 5.7 e le voci di mercato di M2 (5.10, 12.10-12.14).
- **APK 1.4** (1.4.0, versionCode 5, da preparare il 24/11): sull'emulatore 7.8 e, con la correzione KI-165, 2.3; le altre correzioni dell'app della 1.4 sono già OK sull'APK dev (M4 del 23/11).
- **Turno #12**, blocco il 27/11 alle 20:30: 6.7, 7.5, 9.3 «provvisorio» (voti live) e il controllo che chi riposa non riceva «Blocco formazione in arrivo» (KI-102).

**Storico:** fino al 20/11 i blocchi mobile li faceva la sessione «rosario-graceful-feigenbaum» (dalle 08:30 alle 20:30) e il 20/11 c'erano tre controlli del turno vivo sul #11; dal 21/11 li fa «rosario-quirky-marble».

## Come si aggiorna questo file
Ogni mattina, dopo il riepilogo delle 06:17, le voci coperte nella notte cambiano stato nella colonna della piattaforma provata: OK, APERTO (con la riga KI di `known_issues.md`, o il rapporto se la riga non c'è ancora) o NV con il motivo. Una voce APERTO diventa DA RIVERIFICARE quando la correzione è pubblicata. Le funzioni nuove entrano con un codice nuovo nella loro area, DA RIVERIFICARE sulle piattaforme non ancora provate; i codici esistenti non cambiano. Insieme al file si aggiornano il riepilogo qui sopra e i dati della pagina di stato. Le corse non scrivono nel repository: aggiorna la sessione che coordina il lavoro. Quando un'area non ha più voci DA FARE o DA RIVERIFICARE, la sua corsa notturna si può spegnere o diradare, come A e C dal 22/11 e B dal 24/11.
