# Copertura dei test QA e scaletta (web e mobile)

Aggiornato il 23/11/2026 (prima: 22/11, e prima ancora 18/11) con:
- i blocchi M3, M4 e M5 del 22/11 sull'emulatore del PC di Rosario;
- le cinque corse della notte 22→23/11 (22:23, 00:43, 01:53, 03:03 e 04:13; il Gruppo A quella notte non parte);
- `known_issues.md` al 23/11: le correzioni della notte 21→22/11 (KI-118 … KI-123) e i problemi nuovi della notte 22→23/11, in correzione (KI-147 … KI-151).

Prima, il 22/11: i rapporti del 21/11 (verifica sulla 1.2, blocchi M1-M5), le corse 00:43, 01:53 e 03:03 della notte 20→21/11 e le sei corse della notte 21→22/11.

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
- **Ultima:** data dell'ultima prova (per le corse notturne, la data del piano: la notte 21→22/11 è il 22/11). «12-18/11» vuol dire provata fra il 12 e il 18/11.
- **KI-N:** riga N della tabella di `known_issues.md` (numero di riga del file al 23/11).
- **Prerequisiti:**
  - **[PREP]**: serve la lega preparata (vedi sotto);
  - **[OPER]**: serve un account operatore;
  - **[VIVO]**: serve un turno con calcio d'inizio vicino.

## Riepilogo al 23/11

Giudizio per voce: **fatto** se tutte le piattaforme che la riguardano sono OK; **problema aperto** se almeno una è APERTO; **da ricontrollare** se almeno una è DA RIVERIFICARE; **manca** se almeno una è DA FARE; **non verificabile** se il resto è NV.

| Area | Voci | Fatto | Manca | Da ricontrollare | Problema aperto | Non verificabile |
|---|---|---|---|---|---|---|
| 1. Accesso, profilo, privacy | 16 | 11 | 0 | 3 | 1 | 1 |
| 2. Leghe, inviti, partecipanti | 12 | 7 | 2 | 0 | 2 | 1 |
| 3. Rosa, listone, crediti | 14 | 12 | 0 | 0 | 1 | 1 |
| 4. Mercato: scambi | 11 | 8 | 1 | 0 | 1 | 1 |
| 5. Mercato: aste e svincolati | 12 | 7 | 2 | 0 | 2 | 1 |
| 6. Formazione | 8 | 7 | 1 | 0 | 0 | 0 |
| 7. Turni, calendario, classifica | 7 | 5 | 1 | 1 | 0 | 0 |
| 8. Notifiche | 9 | 8 | 0 | 0 | 0 | 1 |
| 9. Web | 5 | 4 | 0 | 0 | 1 | 0 |
| 10. App mobile (browser ed emulatore) | 9 | 4 | 2 | 0 | 2 | 1 |
| 11. Salute e prestazioni | 3 | 3 | 0 | 0 | 0 | 0 |
| 12. App Android: azioni sull'app (solo EMU) | 25 | 18 | 6 | 0 | 1 | 0 |
| **Totale** | **131** | **94** | **15** | **4** | **11** | **7** |
| Totale al 18/11 | 124 | 33 | 66 | 12 | 5 | 8 |

**Problemi nuovi della notte 22→23/11** (in `known_issues.md` dal 23/11, tutti in correzione il 23/11 con l'approvazione di Rosario):
- **KI-147**, corsa 04:13, voce 3.12 (W390), gravità alta: la correzione KI-100 non tiene più, in Rosa › Storico la tabella «Intervalli di possesso» è tagliata a 390 px;
- **KI-148**, corsa 03:03, voce 2.7 (MobB, EMU), media: nell'app «Elimina lega» da Amministrazione lega elimina la lega, poi mostra la schermata d'errore;
- **KI-149**, corsa 03:03, voce 10.1 (MobB), bassa: un membro che apre Fantallenatori fa 2 richieste di amministrazione che rispondono 403;
- **KI-150**, corsa 03:03, voce 5.9 (MobB), bassa: nell'app «Spareggio aperto/annullato» stanno sotto «Scambi» invece che sotto «Asta»;
- **KI-151**, corse 03:03 e 04:13, voce 9.3 (W1280, W390), bassa: sul campo la pastiglia «s.v.» è grigio scuro invece del gradiente viola.

Dal blocco M5 del 22/11 resta aperta anche la voce 12.23 (KI-142): l'app avviata senza rete mostra l'accesso senza messaggio e non riparte quando la rete torna (da correggere nella 1.3).

I problemi del 22/11 (D1, P1, P3, P4) sono corretti e riprovati OK il 23/11 (KI-118, KI-119, KI-120, KI-122); P2 (KI-123, voce 10.2) è da fare nella 1.3.

## Prerequisiti da preparare una volta sola

1. **Lega preparata `QA-PREP-PARI`** (PRONTA dal 18/11: id `d96590b8-37e2-4eff-9f7b-e24dccf8370d`, attiva, 8 × 35, 31 turni europei, 21 giornate; rose fatte con l'import CSV, perché il riempimento casuale vale solo per i fantallenatori IA), da tenere e non cancellare:
   - 8 partecipanti (`qa-01` admin, poi `qa-02`…`qa-08`) e competizioni Serie A, Premier e LaLiga;
   - rose complete a 35, lega **attivata**, così ci sono calendario e turni veri;
   - serve a tutte le voci [PREP]. Le corse possono usarla, ma non devono eliminarla né modificarne le regole;
   - **al 23/11 il turno #11 è ancora bloccato (dal 20/11) e non omologato**: mancano le 3 partite della sera del 23/11. Finché resta così, mercato e scambi sono fermi (`market_round_in_progress`) e non si possono provare 4.7, 5.7, 5.10 e 12.11-12.14.
2. **Lega preparata `QA-PREP-DISPARI`** (PRONTA dal 18/11: id `7a1b25b2-acfc-4ff3-a433-8056a7766330`, attiva, 5 × 35) con 5 partecipanti (`qa-01`…`qa-05`): serve al calendario dispari dal vivo.
3. **Account operatore QA:** `qa-09@test.fantappero.it` (stessa password degli altri), PRONTO dal 18/11: le voci [OPER] si provano con `qa-09`.
4. **Turno vivo:** il prossimo è il **#12**, primo calcio d'inizio il **27/11 alle 20:45** (ora di Roma), blocco della formazione alle **20:30**. In `QA-PREP-DISPARI` riposa `qa-02` nella giornata 12.
5. **Pulizia:** su dev restano due leghe di prova attive di corse passate, `QA-2026-11-19-0153-B` e `QA-2026-11-21-0413-B` (admin `qa-01`), e una in configurazione, `QA-2026-11-21-0043-B` (admin `qa-05`, vista dalla corsa 04:13 del 23/11): le può eliminare l'operatore `qa-09`.

## Area 1 – Accesso, profilo, privacy

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Registrazione: campi, email duplicata, risposta generica | OK | – | – | – | – | 12-18/11 |  |
| 1.2 | Password comuni o uguali all'email rifiutate (decisione 12) | OK | DA RIVERIFICARE | – | OK | – | 23/11 | API OK il 22/11 (corsa 23:33): `password_too_common`, `password_same_as_email` anche in maiuscolo; nel reset la password comune è rifiutata prima del controllo del token (per l'uguale all'email nel reset serve un token vero). MobB OK il 23/11 (corsa 03:03; nell'app non c'è il cambio password dal profilo). Da rivedere il messaggio a schermo su W1280 |
| 1.3 | Login, logout che chiude subito il token, refresh e catena | OK | – | – | – | – | 22/11 | riprovato il 22/11 |
| 1.4 | Profilo: nome, nickname (sosia Unicode, punteggiatura) | OK | – | – | – | – | 22/11 | 22/11: nickname cirillico e nome oltre 80 caratteri rifiutati (sul profilo 400 invece di 422: solo incoerenza, suggerimento) |
| 1.5 | Nickname univoco contro un altro account | OK | – | – | – | – | 22/11 | rifiutati anche maiuscole, larghezza piena, spazi, accenti e NFD (`nickname_taken`); il nickname lasciato torna libero |
| 1.6 | Avatar: solo immagine vera, `nosniff` (decisione 13) | OK | – | – | – | DA RIVERIFICARE | 22/11 | API OK il 22/11: PNG con HTML → 400 `invalid_avatar_format`, script accodato tolto, servito con `nosniff`. EMU: avatar scelto dalla galleria ancora da riprovare |
| 1.7 | Preferenze notifiche, quiet hours, esportazione dati | OK | – | – | – | – | 22/11 | 22/11: un PATCH rifiutato non salva nulla; preferenze per categoria ed evento rispettate (corsa 01:53) |
| 1.8 | Eliminazione account vera | OK | – | – | – | – | 22/11 | account usa e getta: senza password `invalid_password`, con la password eliminato, poi login 401 e nickname libero. Dall'app: 12.4 |
| 1.9 | Informativa privacy a schermo | – | OK | OK | OK | OK | 21/11 | W1280 e W390 il 21/11 (link in accesso e registrazione, margini di `/privacy`); MobB 21/11 (corsa 03:03); EMU 21/11 (M1, versione 2026-11c) |
| 1.10 | Rate limit registrazione e login | OK | – | – | – | – | 12-18/11 |  |
| 1.11 | Login, logout e sessione dopo il riavvio dell'app | – | – | – | – | OK | 22/11 | flusso 04 passato anche il 21 e il 22/11 (M5) |
| 1.12 | Accesso con email nell'app | – | – | – | – | OK | 22/11 | flusso 01 passato più volte il 21/11 e di nuovo il 22/11 (M5) |
| 1.13 | Link di verifica email e di reset password aperti dall'app | – | – | – | – | OK | 18/11 | APK `2633ca4`: link `fantappero://…` e App Link dev `verified`, anche a freddo dal link web |
| 1.14 | PATCH del nickname in parallelo, token push non cancellati all'eliminazione | APERTO | – | – | – | – | 12-18/11 | noto dalla sola lettura del codice (nessuna riga in `known_issues.md`) |
| 1.15 | Email reali, accesso con Google, richiesta di accesso dei non tester | NV | – | – | – | – | – | su dev: email non reali e modalità test spenta (non va accesa) |
| 1.16 | **Nuova (21/11, KI-107).** Informativa accettata anche con l'accesso con email | OK | DA RIVERIFICARE | – | OK | OK | 23/11 | API 22/11 (`policyVersion` 2026-11c dopo l'accesso con email: corse 23:33 e 04:13); EMU 21/11 (profilo: «Hai accettato l'informativa privacy (versione 2026-11c)…»); MobB OK il 23/11 (corsa 03:03). Da vedere il messaggio del profilo sul sito |

## Area 2 – Leghe, inviti, partecipanti

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 2.1 | Creazione lega, preset, crediti iniziali, codice invito e adesione | OK | – | – | – | – | 22/11 | rifatto in ogni corsa per preparare le leghe di prova; il mercato resta chiuso finché la lega non è al completo (KI-93) |
| 2.2 | Invito nominale: accetta, rifiuta, revoca, duplicati | OK | – | – | – | – | 22/11 | 22/11: «Annulla invito» toglie la notifica; posti riservati agli inviti in attesa (`league_full`); notifiche d'invito senza doppioni |
| 2.3 | Gli stessi flussi a schermo | – | DA FARE | DA FARE | OK | OK | 23/11 | EMU OK il 21/11 (M1: registrazione, accesso, ingresso in lega; vedi 12.6 e 12.7). MobB OK il 23/11 (corsa 03:03: creazione, ingresso con codice, invito nominale rifiutato e poi accettato). Il 22/11 la corsa 23:33 l'ha saltata (campione della domenica) |
| 2.4 | Ingresso con link di invito aperto dall'app | – | – | – | – | OK | 18/11 | da collegato e da scollegato; il link web apre direttamente l'app |
| 2.5 | Elenco partecipanti, ruoli, permessi admin e non membro | OK | – | – | – | – | 22/11 | 22/11: un membro riceve 403 su tutte le azioni da admin |
| 2.6 | Sostituzione partecipante | OK | – | – | – | – | 22/11 | squadra, rosa e crediti passano al nuovo; il vecchio riceve 403; l'invito pendente del nuovo si chiude. Da decidere: chi è stato sostituito può rientrare col codice se resta un posto |
| 2.7 | Eliminazione lega da admin (bozza) | OK | – | – | APERTO | APERTO | 23/11 | API OK il 22/11. APERTO nell'app (KI-148, corsa 03:03 del 23/11, in correzione): «Elimina lega» da Amministrazione lega elimina la lega (204) ma poi mostra «Qualcosa è andato storto» (errore React #300); visto su MobB, il codice è lo stesso dell'app Android |
| 2.8 | Eliminazione lega da operatore, a schermo [OPER] | – | OK | – | NV | DA FARE | 23/11 | W1280 il 22/11 con qa-09 (il 21/11 anche conferma e annulla, a 1280 e 390). MobB NV il 23/11: la conferma di «Elimina» usa `Alert.alert`, che nel browser non si apre. EMU: pulsante «Elimina» del pannello operatore dell'app (KI-68) |
| 2.9 | Notifica "Lega eliminata" vista davvero | OK | OK | – | OK | – | 23/11 | API e W1280 il 22/11: una notifica per membro, nessuna a chi elimina, preferenza spenta rispettata, link `/`. MobB OK il 23/11 (corsa 03:03) |
| 2.10 | Codici 400 invece di 403/404, badge inviti con la lega in asta | APERTO | – | – | – | – | 12-18/11 | KI-11 (stile, nessuna fuga di dati) |
| 2.11 | Scadenza reale di un invito | NV | – | – | – | – | – | il minimo è 1 giorno |
| 2.12 | **Nuova (22/11).** Notifica «Nuovo invito» tolta quando la lega viene eliminata | OK | – | – | – | – | 23/11 | difetto P1 del 22/11 corretto (KI-119) e riprovato OK il 23/11 (corsa 04:13): «Nuovo invito» tolto e «Lega eliminata» ricevuta dall'invitato |

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
| 3.11 | Movimenti crediti = saldo, storico rosa, esubero in attesa | OK | – | – | – | – | 23/11 | 23/11 (corse 00:43 e 04:13): saldo = saldo ricostruito = somma dei movimenti per 22 squadre; note dei movimenti, vecchie e nuove, con i nomi giusti («Acquisto L. Jovanović», «Acquisto D. O'Shea»): D1 del 22/11 corretto (KI-118). Note vecchie rovinate da riparare in lettura: NV, non ce ne sono più |
| 3.12 | Rosa e crediti a schermo con una rosa piena [PREP] | – | OK | APERTO | OK | OK | 23/11 | i difetti del 21/11 (nome dell'esubero nascosto a 390, tabelle da scorrere a 1280, nomi tagliati nel listone a 390) sono corretti (KI-100, KI-104) e riprovati OK il 21-22/11; MobB 21/11; EMU 21/11 (M2). APERTO a 390 (KI-147, corsa 04:13 del 23/11, in correzione): in Rosa › Storico la tabella «Intervalli di possesso» è tagliata, «Al» e «Fonte» irraggiungibili (la correzione KI-100 non tiene più). A 1280 e le tabelle per ruolo a 390 OK |
| 3.13 | **Nuova (21/11, KI-106 e KI-112).** Listone: filtri «Campionato» e «Squadra», «Azzera filtri» | – | OK | OK | OK | OK | 23/11 | W1280 OK il 22/11 (corsa 04:13); EMU OK il 22/11 (M3, «Azzera filtri» riporta anche il ruolo, KI-112); W390 e MobB OK il 23/11 (corse 00:43 e 03:03). «Azzera filtri» lascia ricerca e «Solo disponibili» per scelta (KI-138). Menu «Campionato» nascosto con un solo campionato: NV, una lega ne richiede almeno 3. I filtri sono solo su sito e app, non nell'API; non ancora nel listone dell'operatore |
| 3.14 | **Nuova (21/11, KI-113).** Avviso quando un ruolo è al completo | OK | OK | OK | OK | OK | 23/11 | API 22/11: rifiuto a ruolo pieno, conteggio uguale al server. EMU 21/11 (APK `04cc83b`): «Portieri al completo: 3 su 3…», swipe bloccato con il motivo, il ruolo torna libero dopo lo svincolo. W1280, W390 e MobB OK il 23/11 (corsa 00:43, portieri 3/3 con altri posti liberi): avviso per membro e admin, «+» disattivati con il motivo, swipe «Pieno» su MobB |

## Area 4 – Mercato: scambi

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 4.1 | Proposta, accetta, rifiuta, annulla, controproposta, scadenza | OK | – | – | – | – | 12-18/11 |  |
| 4.2 | Concorrenza (doppia accettazione, deadlock) | OK | – | – | – | – | 18/11 | corretto il 18/11 |
| 4.3 | Approvazione dell'admin, notifiche e link | OK | – | – | – | – | 12-18/11 |  |
| 4.4 | Rifiuto che chiude il pannello, a schermo | – | OK | OK | – | – | 21/11 | corsa 03:03 del 21/11, anche la controproposta |
| 4.5 | Filtri Ricevute/Inviate/In corso/Tutte e statistiche, a schermo | – | OK | OK | OK | OK | 21/11 |  |
| 4.6 | "Non più valida" e "+ N in attesa di crediti", a schermo | – | OK | OK | OK | – | 21/11 |  |
| 4.7 | Scambio sbilanciato a rosa piena 35/35 ed esubero di ruolo [PREP] | DA FARE | – | – | – | – | – | il 22/11 non si poteva fare: il turno 11 di `QA-PREP-PARI` è ancora bloccato e non omologato, scambi fermi (`market_round_in_progress`). Stato della rosa coerente su `/rosa` e `/squadre` |
| 4.8 | Scambi chiusi a turno in corso (`round_freeze`) | OK | OK | OK | OK | OK | 22/11 | API 22/11: proposta, accettazione e controproposta → 400 `market_round_in_progress`; a schermo il 21/11 «Mercato fermo: turno in corso» (KI-102) su sito, MobB ed EMU |
| 4.9 | Proporre uno scambio dall'app e riceverne la notifica | – | – | – | – | OK | 18/11 | il 21/11 il flusso 07 è fallito solo perché il mercato era fermo |
| 4.10 | Limite proposte aggirabile con l'approvazione admin | APERTO | – | – | – | – | 12-18/11 | KI-21, da decidere |
| 4.11 | Scambio con un non membro | NV | – | – | – | – | – | manca un account esterno |

## Area 5 – Mercato: aste e svincolati

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 5.1 | Buste: sessione, offerta, ritiro, chiusura, risoluzione, spareggio | OK | – | – | – | – | 22/11 | il 22/11 sessione, offerte, spareggio e risoluzione di nuovo OK (corsa 22:23) |
| 5.2 | Spareggio che finisce di nuovo in parità | OK | – | – | – | – | 22/11 | vince l'offerta inviata per prima, nessun secondo spareggio, un solo addebito (decisione del 19/11) |
| 5.3 | Waiver in parità | OK | – | – | – | – | 22/11 | vince chi ha inviato per primo; «Spareggio svincolati aperto/annullato», «Svincolato aggiudicato/perso» |
| 5.4 | Live: manuale, sequenziale, rilanci, timer, aggiudicazione | OK | – | – | – | – | 22/11 | 22/11 sera (corsa 22:23): lotto live manuale aggiudicato con un solo addebito, seconda aggiudicazione 400 `market_live_lot_closed`, saldo = somma dei movimenti; nota «Assegnazione da asta a rilanci» (KI-85) giusta, anche nello storico della Rosa a 1280 |
| 5.5 | Live: giro completo `turn_based` | OK | – | – | – | – | 22/11 | fuori turno → 400 `market_live_not_your_turn`; «salta» e «annulla» consumano il turno, come deciso |
| 5.6 | Live: leader senza crediti all'aggiudicazione | OK | – | – | – | – | 22/11 | il lotto va all'offerta successiva valida, o passa; un solo addebito; «Lotto perso: crediti insufficienti» |
| 5.7 | Live: scambio immediato a rosa 35/35 [PREP] | DA FARE | – | – | – | – | – | il 22/11 non si poteva fare: l'asta live non si apre con il turno 11 in corso. Lo scambio a ruolo pieno è OK (5.9) |
| 5.8 | Selettore calciatori dell'asta (buste e live), a schermo | – | OK | OK | OK | – | 22/11 | buste e coda live OK il 21/11; scelta del calciatore da chiamare in un'asta live aperta OK a 1280 il 22/11 sera (corsa 22:23: ricerca, filtri per ruolo, pagine, «Chiama» disattivato senza scelta). Suggerimento: a 1280 la riga dei filtri per ruolo è tagliata a destra |
| 5.9 | Avvisi "Spareggio annullato", busta "non assegnabile", "Scelta richiesta: rosa al completo" visti davvero | OK | – | – | APERTO | – | 23/11 | API il 22/11 (corsa 22:23). MobB 23/11 (corsa 03:03): gli avvisi arrivano e il link `/asta` è giusto, ma APERTO KI-150 (in correzione il 23/11): nel centro notifiche dell'app «Spareggio aperto/annullato» stanno sotto «Scambi» invece che sotto «Asta» |
| 5.10 | Fare un'offerta in busta dall'app [PREP] | – | – | – | – | DA FARE | – | il 21/11 non si poteva fare: mercato fermo per il turno 11. Serve una sessione a buste aperta in `QA-PREP-PARI` (la apre l'admin `qa-01`) |
| 5.11 | Rimborso del calciatore svincolato con il waiver | APERTO | – | – | – | – | 22/11 | KI-23, da decidere; ancora presente il 22/11 |
| 5.12 | Risoluzione concorrente vera | NV | – | – | – | – | – | regola: una richiesta alla volta per account |

## Area 6 – Formazione

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 6.1 | Moduli, titolari, panchina, validazioni server | OK | – | – | – | – | 12-18/11 |  |
| 6.2 | Bozza: al massimo 11 titolari, 1 portiere e i ruoli del modulo; DELETE solo a turno aperto | OK | – | – | – | – | 22/11 |  |
| 6.3 | Bloccati, indisponibili, fuori rosa | OK | – | – | – | – | 22/11 | bloccati e fuori rosa OK; indisponibili reali NV (nessuno nei dati di dev) |
| 6.4 | Copia formazione precedente | OK | – | – | – | – | 22/11 | non ancora visto il caso di un calciatore uscito dalla rosa dopo la formazione salvata |
| 6.5 | Salvare la formazione a schermo [PREP] | – | – | OK | OK | OK | 23/11 | W390 il 21/11; EMU flusso 06 il 21 e 22/11. MobB OK il 23/11 (corsa 03:03: salvataggio 200, «Formazione salvata.» sul turno 11, senza modifiche; da controllare via API se il server accetta modifiche vere a calciatori già bloccati). Resta da decidere `canChangeTurn`: un membro non può scegliere il turno 12 mentre è in corso l'11 (corsa 00:43) |
| 6.6 | Esubero di ruolo in formazione [PREP] | OK | – | – | – | – | 22/11 | `athlete_exceeds_role_quota` con il nome; in tribuna viene tolto senza errore |
| 6.7 | Blocco progressivo, mosse tattiche, formazione automatica al primo blocco [PREP][VIVO] | DA FARE | – | – | – | – | 21/11 | 21/11: blocco progressivo del turno 11 OK in lettura; formazione automatica e margine di blocco ancora da vedere. Prossimo turno vivo: #12, blocco il 27/11 alle 20:30 |
| 6.8 | Formazione dell'operatore [OPER] | OK | – | – | – | – | 21/11 |  |

## Area 7 – Turni, calendario, classifica

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 7.1 | Calendario pari, partite del turno, soglia partite, reinclusione | OK | – | – | – | – | 12-18/11 |  |
| 7.2 | Calendario dispari dal vivo [PREP] | OK | – | – | – | – | 22/11 | con `QA-PREP-DISPARI`: un riposo per giornata a rotazione, ogni coppia una volta per ciclo |
| 7.3 | Attivazione lega: blocco per crediti | OK | – | – | – | – | 22/11 | blocchi per rose incomplete e calendario mancante OK; un saldo negativo non si raggiunge da nessuna strada dell'API (il blocco per crediti è solo una difesa) |
| 7.4 | Cutoff, ricalcolo, apertura manuale del turno, omologazione, correzioni [OPER] | OK | – | – | – | – | 22/11 | con qa-09. Da decidere: l'operatore può omologare un turno giocato prima che la lega esistesse |
| 7.5 | Notifiche "formazione in scadenza" e "blocco imminente" [PREP][VIVO] | DA RIVERIFICARE | – | – | DA FARE | OK | 21/11 | il 21/11 (corsa 01:53) gli avvisi indicavano il calcio d'inizio invece del blocco e dicevano «della tua formazione»: corretti il 21/11 (KI-101, pilota-1.2). EMU 21/11: testo nuovo OK («4 calciatori della tua rosa si bloccano alle …»). Da rivedere al blocco del 27/11: orario, arrivo prima del blocco, nessun avviso a chi riposa (KI-102) |
| 7.6 | Turni, calendario e classifica a schermo con una lega attiva [PREP] | – | OK | OK | OK | OK | 22/11 | il 21/11 un turno iniziato restava «Prossimo» (KI-101): corretto e riprovato OK (W1280 e W390 il 22/11, MobB il 21/11). «Turno saltato» OK su sito e MobB; EMU 21/11 (M3) |
| 7.7 | Risultati, voti, fantapunti, classifica, scontro diretto | DA FARE | DA FARE | – | – | – | 23/11 | 23/11 (corsa 01:53): provvisori del turno 11 coerenti su API e W1280 (totali = somma dei titolari, nessuna sostituzione prima della fine del turno, scontri 0 gol e pareggio sotto 66, classifica a 0 perché nessuno scontro è definitivo). 4 partite del 22/11 ancora senza voti (ritardo del fornitore). Da fare dopo le 3 partite del 23/11 sera: definitivi, sostituzioni automatiche, omologazione e classifica; anche `QA-PREP-DISPARI`. Da decidere: «S.V.» con `scoreFinal` già vero quando i voti non sono ancora arrivati |

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
| 9.3 | Contrasti del tema chiaro e scuro | – | APERTO | APERTO | – | – | 23/11 | tribuna e ambra «attenzione» (KI-98, KI-99) OK il 21-23/11; nomi dei titolari «senza voto» e «s.v.» delle sfide a 5,38:1 (P3 corretto, KI-120) OK il 23/11 (corse 03:03 e 04:13). APERTO KI-151 (in correzione il 23/11, solo aspetto): sul campo la pastiglia «s.v.» è grigio scuro invece del gradiente viola, e sparisce anche quello di «provvisorio» (contrasto circa 15:1) |
| 9.4 | Pagine nuove: "+ Tester" con liste impaginate, "Elimina" lega, "Rimetti nel turno" ("+ Tester" ed "Elimina" sono [OPER]) | – | OK | OK | – | – | 23/11 | «+ Tester» ed «Elimina» OK il 21/11 (impaginazione dei tester NV: solo 3 tester). «Rimetti nel turno» senza calendario diceva «Il ricalcolo non è riuscito»: corretto il 21/11 (KI-101), OK a 1280 il 22/11 e a 390 il 23/11 (corsa 03:03: «Escludi» e «Rimetti nel turno» 200 con i loro messaggi) |
| 9.5 | Pagine principali con una lega attiva e rose piene [PREP] | – | OK | OK | – | – | 23/11 | 16 pagine OK il 21-22/11. P4 del 22/11 (Amministrazione di una lega attiva con «Prima salva la configurazione…» e «Invitati» disattivata) corretto (KI-122) e riprovato OK il 23/11 a 1280 e 390 (corse 03:03 e 04:13, 15 pagine senza errori) |

## Area 10 – App mobile (browser ed emulatore)

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 10.1 | Schermate principali senza errori | – | – | – | APERTO | OK | 23/11 | MobB OK il 21-23/11 (Svincolati nascosta per scelta); EMU flusso 02 il 21 e 22/11. APERTO su MobB (KI-149, corsa 03:03 del 23/11, in correzione): un membro che apre Fantallenatori fa 2 richieste di amministrazione che rispondono 403 (2 errori in console, lo schermo «Permessi insufficienti» resta giusto); il codice è lo stesso dell'app Android |
| 10.2 | Schermate principali con contenuti di lega [PREP] | – | – | – | APERTO | OK | 22/11 | EMU 21/11 (M3). APERTO su MobB: nella Home lega la scheda «Campionati» è tagliata («La Liga · Premier Leagu…»), difetto P2 della corsa 03:03 del 22/11 (KI-123, da fare nella 1.3: serve un APK); probabile anche sull'app vera |
| 10.3 | Pannello operatore mobile [OPER] | – | – | – | OK | DA FARE | 21/11 | MobB 21/11 con qa-09: navigazione OK, «Elimina» lega da provare (2.8); notifiche operatore NV (nessuna) |
| 10.4 | Coerenza con il web: etichette, stati scambi, colori ruolo, causali crediti | – | – | – | OK | – | 22/11 | MobB contro W390 il 21 e 22/11; colori di ruolo della stessa tinta ma di tonalità diverse (suggerimento) |
| 10.5 | Schermata di accesso: tema chiaro, bandiera Premier, tastiera, titolo | – | – | – | – | OK | 18/11 | anche «GIOCA» leggibile |
| 10.6 | Galleria e fotocamera per l'avatar | – | – | – | – | DA FARE | 18/11 | galleria OK il 18/11 («Avatar aggiornato.»); fotocamera ancora da provare (anche con la fotocamera virtuale dell'emulatore) |
| 10.7 | Push vere, Google nativo | – | – | – | – | NV | – | serve un telefono vero (l'emulatore non ha Play Store) |
| 10.8 | **Nuova (21/11, KI-111).** Avviso di nuova versione dell'app | OK | OK | – | – | OK | 23/11 | EMU 21/11 (M5): nessun avviso senza versione impostata; con 1.3.0/4 «È disponibile la versione 1.3 dell'app.» con «Scarica» e «Più tardi» (che non lo ripropone); torna con 1.4.0/5. API: qa-08 riceve 403 su `/admin/app-version`, lettura OK il 22/11. W1280 OK il 23/11 con qa-09 (corsa 03:03: si apre «Versione dell'app Android», nulla salvato). Su dev il link è di prova (`example.com`) |
| 10.9 | **Nuova (21/11, KI-114).** «Segnala un problema»: pagina giusta e versione dell'app | OK | OK | – | – | OK | 23/11 | EMU 21/11 (APK `04cc83b`): dalla Rosa `Roster` e `1.2.0 (3)`, da una notifica `Formation`; la strada Home lega › Rosa NV (pulsante assente). API OK il 22/11. W1280 OK il 23/11 con qa-09 (corsa 03:03: pagina e versione visibili nelle segnalazioni). Restano su dev segnalazioni di prova da chiudere a mano |

## Area 11 – Salute e prestazioni

| Cod | Voce | API | W1280 | W390 | MobB | EMU | Ultima | Note |
|---|---|---|---|---|---|---|---|---|
| 11.1 | `/live`, `/ready`, letture sotto 2 s, nessun 5xx | OK | – | – | – | – | 22/11 | scritture lente: conferma dell'import CSV 6-8,3 s per 105-140 righe, regolamento 5 s, sincronizza 9,5 s, riempimento 6 s |
| 11.2 | Tempi su una lega attiva con rose piene [PREP] | OK | – | – | – | – | 22/11 | letture al massimo 0,77 s, nessun dato altrui esposto |
| 11.3 | `/realtime/stream` | OK | – | – | – | – | 22/11 | si apre, riceve un evento in circa 1 s, 401 senza token |

## Area 12 – App Android: azioni sull'app (solo EMU)
Le aree 1-8 sono state provate quasi sempre via API. Qui ci sono le stesse funzioni fatte **dall'app**, più le cose che esistono solo su un telefono. Quando serve l'altra parte (per esempio chi riceve uno scambio), quella si fa via API con un altro account QA.

| Cod | Voce | EMU | Blocco | Ultima | Note |
|---|---|---|---|---|---|
| 12.1 | Registrazione dall'app con un account usa e getta, messaggio di verifica | OK | M1 | 21/11 | nessun messaggio di verifica: su dev la conferma dell'email è spenta per scelta (KI-73) |
| 12.2 | "Password dimenticata" dall'app | OK | M1 | 21/11 | compare «Controlla la tua email» |
| 12.3 | Profilo: nome, nickname, preferenze notifiche, ore di silenzio, tema chiaro e scuro | DA FARE | M1 | 21/11 | 21/11: nome salvato e tema scuro subito su tutto (KO-1, KI-70) OK; mancano nickname (Maestro non scriveva nel campo), notifiche, ore di silenzio e il ritorno al tema chiaro |
| 12.4 | Esportazione dati ed eliminazione account dall'app (account usa e getta) | OK | M1 | 21/11 | eliminazione OK; l'esportazione nell'app non c'è per scelta (KI-71: la copia dei dati si chiede a info@fantappero.it) |
| 12.5 | Sessione: app in background per più di 30 minuti e ritorno (rinnovo del token), poi riavvio | OK | M1 | 21/11 | 52 minuti in background, poi riavvio: sempre collegata. Al ritorno mostrava la home di una lega già eliminata finché non si navigava |
| 12.6 | Creare una lega dall'app (nome, competizioni, regole) | OK | M1 | 21/11 |  |
| 12.7 | Ingresso con codice; invito nominale ricevuto, accettato e rifiutato | OK | M1 | 21/11 | da fare a parte: «Annulla invito» dall'app dell'admin (KI-68, vedi la scaletta di M1) |
| 12.8 | Partecipanti, directory fantallenatori, cambio della lega attiva [PREP] | OK | M1 | 21/11 | anche l'email dei fantallenatori visibile solo all'admin (KI-92) |
| 12.9 | Listone: filtro ruolo, ricerca, "Solo disponibili" [PREP] | OK | M2 | 22/11 | ricerca e filtro ruolo OK il 21/11; «Solo disponibili» OK il 22/11 (M3) |
| 12.10 | Admin dall'app: assegnazione manuale di uno slot, svincolo con rimborso [PREP] | DA FARE | M2 | 21/11 | assegnazione OK il 21/11; manca lo svincolo con rimborso |
| 12.11 | Scambi dall'app: proponi, accetta, rifiuta, annulla, controproposta [PREP] | DA FARE | M2 | – | il 21/11 non si poteva fare: mercato fermo per il turno 11. Provare anche la conferma «Accetta scambio» (KI-80) e «Nuova proposta» che resta aperta con l'errore (KI-99) |
| 12.12 | Approvazione admin di uno scambio dall'app [PREP] | DA FARE | M2 | – | mercato fermo il 21/11 |
| 12.13 | Asta a buste dall'app: offerta, ritiro, esito [PREP] | DA FARE | M2 | – | mercato fermo il 21/11; controllare anche gli orari in ora italiana (KI-78) |
| 12.14 | Asta live dall'app: rilancio, timer, aggiudicazione (gli altri rilanciano via API) [PREP] | DA FARE | M2 | – | mercato fermo il 21/11 |
| 12.15 | Movimenti crediti e causali [PREP] | OK | M2 | 21/11 | «Aggiustamento admin», «Assegnazione …», «Acquisto rosa» con data e saldo |
| 12.16 | Formazione: modulo, titolari, panchina e ordine, bozza, copia della precedente [PREP] | OK | M3 | 22/11 | 21/11 a turno in corso: modulo, titolari, panchina, «Bozza», «Salva» e «Svuota formazione» OK; 22/11 (M3): cambio modulo che tiene i titolari (KI-77), copia della precedente, esubero in tribuna (KI-84), «Sistema la panchina», «Svuota» e «Ripristina» OK |
| 12.17 | Calciatori bloccati o indisponibili visibili ma non selezionabili [PREP] | OK | M3 | 21/11 | lucchetto e niente «Cambia», in campo e in panchina |
| 12.18 | Turni europei, calendario, scontro diretto, classifica [PREP] | OK | M3 | 22/11 | «In corso» OK il 21/11; «Turno saltato» visto nell'app il 22/11 (M3, KI-102); il motivo del salto non compare ancora (KI-134, nella 1.3) |
| 12.19 | Centro notifiche: badge, segna letta, segna tutte lette | OK | M4 | 22/11 | badge «9+», non lette e segna letta al tocco OK il 21/11; l'avviso «Novità» dell'operatore arriva, anche programmato; «Segna tutte lette» OK il 22/11 (M4: da 18 a 0) |
| 12.20 | Preferenze notifiche e ore di silenzio rispettate | OK | M4 | 22/11 | preferenze rispettate il 22/11 (M4). Ore di silenzio NV: valgono solo per email e push, che sull'emulatore non arrivano (8.8) |
| 12.21 | Tasto "indietro" di Android su ogni schermata: non esce dall'app per sbaglio e non perde i dati inseriti | OK | M5 | 22/11 | tasto indietro OK il 22/11 (M5); non provata la perdita dei dati inseriti in un modulo |
| 12.22 | Accessibilità: testo grande (scala 1,3) e TalkBack sui pulsanti principali | OK | M5 | 22/11 | testo grande (scala 1,3) OK il 22/11 (M5); TalkBack NV sull'emulatore |
| 12.23 | Rete assente o lenta (modalità aereo): messaggi d'errore e ripresa | APERTO | M5 | 22/11 | 22/11 (M5), KO parziale (KI-142, da correggere nella 1.3): avviata in modalità aereo l'app mostra l'accesso («Bentornato») senza messaggio di rete e resta lì quando la rete torna; con l'app già aperta «Connessione non disponibile» e «Ricarica» funzionano |
| 12.24 | Tema chiaro e scuro su tutte le schermate principali | OK | M5 | 22/11 | Profilo in tema scuro il 21/11; tutte le schermate principali leggibili in tema scuro il 22/11 (M5) |
| 12.25 | Schermo più piccolo: l'AVD `maestro_e2e` (Pixel 5) | OK | M5 | 21/11 | tutte le prove del 21/11 su questo AVD, senza problemi di impaginazione |

## Scaletta

### Notte (corse cloud, dalle 22:23 alle 04:13)
Ogni corsa prova, nelle sue aree e nella colonna della sua piattaforma, prima le voci DA FARE senza prerequisiti mancanti, poi le DA RIVERIFICARE. Se le restano risorse, ripassa quelle con il prerequisito appena pronto. L'app nel browser (MobB) e la coerenza con il web a 390 px (10.4) restano alla corsa delle 03:03.

**Gruppi A e C a notti alterne** (decisione di Rosario del 22/11):
- il Gruppo A (23:33) parte solo nei giorni dispari del mese;
- il Gruppo C (01:53) parte solo nei giorni dispari del mese, cioè nelle notti che cominciano in un giorno pari;
- per esempio, la notte 22→23/11 fa solo C (alle 01:53 del 23), la notte 23→24/11 solo A (alle 23:33 del 23).

| Corsa | Quando | Aree | Voci per le prossime notti |
|---|---|---|---|
| 22:23 Mercato | ogni notte | 4, 5 | 4.7 e 5.7 [PREP] appena il turno 11 di `QA-PREP-PARI` è omologato, prima del blocco del 27/11 |
| 23:33 Gruppo A | giorni dispari | 1, 2 | 1.2 e 1.16 (W1280), 2.3 (W1280, W390) |
| 00:43 Gruppo B | ogni notte | 3, 6 | 3.12 a 390 (Rosa › Storico) appena pubblicata la correzione KI-147; 6.7 [VIVO] dopo il blocco del 27/11 |
| 01:53 Gruppo C | giorni dispari (notti che iniziano in un giorno pari) | 7, 8 | 7.7 (API, W1280) dopo le partite della sera del 23/11 o l'omologazione del turno 11; 7.5 dopo il blocco del 27/11: orario, arrivo prima del blocco, nessun avviso a chi riposa |
| 03:03 Gruppo D | ogni notte | 9, 10, 11 e MobB di tutte le aree | appena pubblicate le correzioni del 23/11: su MobB 2.7 (KI-148), 10.1 (KI-149) e 5.9 (KI-150), 9.3 a W1280 e W390 (KI-151); su MobB 7.5 dopo il blocco del 27/11; 10.2 dopo l'APK 1.3 (KI-123) |
| 04:13 Verifica | ogni notte | tutte | regressioni: le voci «CORRETTI/Risolto/Fatto» degli ultimi 3 giorni di `known_issues.md` e, appena pubblicate, le correzioni del 23/11 (KI-147 … KI-151) |

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
| M1 Accesso, account e leghe | 09:37 | 09:57 | 1.6 (avatar dalla galleria), 12.3; con `qa-09` 2.8 e 10.3 («Elimina» lega, KI-68); «Annulla invito» dall'app dell'admin (KI-68); 10.6 fotocamera; 2.7 «Elimina lega» da Amministrazione lega dopo la correzione KI-148 |
| M2 Rosa e mercato | 12:37 | 12:27 | 12.10 (svincolo con rimborso); a mercato aperto 5.10 e 12.11-12.14 |
| M3 Formazione e turni | 15:25 | 15:27 | nessuna voce DA FARE dal 22/11: solo il ripasso dei flussi Maestro |
| M4 Notifiche | 18:37 | 18:27 | nessuna voce DA FARE dal 22/11: solo il ripasso dei flussi Maestro |
| M5 Sistema e ripasso | 21:37 | 21:27 | tutti i flussi Maestro di `apps/mobile/e2e/maestro/flows/dev/` sull'ultimo APK (il 22/11: da 01 a 06 passati; 07 solo a mercato aperto; 08 va lanciato con `NOTIF_ID`); 12.23 dopo la correzione nella 1.3 (KI-142) |

Ogni blocco dura al massimo un'ora circa: le voci che non riesce a fare passano al giorno dopo, finché nel registro non restano voci DA FARE per quel blocco. Quando un blocco non ha più voci DA FARE, fa solo il ripasso dei flussi Maestro.

Restano NV sul mobile le push vere e l'accesso con Google (8.8, 10.7): l'emulatore non ha Play Store, serve un telefono vero.

### Prossimi appuntamenti
- **Turno #12**, blocco il 27/11 alle 20:30: 6.7, 7.5 e il controllo che chi riposa non riceva «Blocco formazione in arrivo» (KI-102).
- **Dopo il 23/11:** 7.7, risultati definitivi e classifica del turno 11.
- **Dopo l'omologazione del turno 11:** 4.7, 5.7 e le voci di mercato di M2.

**Storico:** fino al 20/11 i blocchi mobile li faceva la sessione «rosario-graceful-feigenbaum» (dalle 08:30 alle 20:30) e il 20/11 c'erano tre controlli del turno vivo sul #11; dal 21/11 li fa «rosario-quirky-marble».

## Come si aggiorna questo file
Ogni mattina, dopo il riepilogo delle 06:17, le voci coperte nella notte cambiano stato nella colonna della piattaforma provata: OK, APERTO (con la riga KI di `known_issues.md`, o il rapporto se la riga non c'è ancora) o NV con il motivo. Una voce APERTO diventa DA RIVERIFICARE quando la correzione è pubblicata. Le funzioni nuove entrano con un codice nuovo nella loro area, DA RIVERIFICARE sulle piattaforme non ancora provate; i codici esistenti non cambiano. Insieme al file si aggiornano il riepilogo qui sopra e i dati della pagina di stato. Le corse non scrivono nel repository: aggiorna la sessione che coordina il lavoro. Quando un'area non ha più voci DA FARE o DA RIVERIFICARE, la sua corsa notturna si può spegnere o diradare, come A e C dal 22/11.
