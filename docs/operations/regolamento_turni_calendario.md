# Regolamento: turni, copertura del 75%, calendario e ruoli del listone

**Stato:** in vigore su dev e pilota dal 22/11/2026 (decisioni di Rosario del 20-22/11).
**A chi serve:** a chi gestisce il pilota (operatore, admin di lega) e come base per la sezione «Domande frequenti» per i fantallenatori (in fondo).
Le regole qui sotto descrivono il comportamento del codice; dove il codice cambia, questo file va aggiornato.

## 1. I turni (Turni europei)

- Il sistema conosce le date di tutte le partite dei campionati scelti dalla lega, fino a fine stagione.
- Da quelle date crea le **finestre dei turni**, per esempio «venerdì-lunedì». Ogni finestra è un **turno**.
- Un turno si **apre** in automatico (si può mettere la formazione) quando mancano al massimo 14 giorni al suo primo blocco, e solo nelle **leghe attive**.
- Ogni calciatore si **blocca** poco prima della sua partita: calcio d'inizio meno il margine della lega, di solito 15 minuti. Dopo il blocco non si può più spostare.

## 2. La regola del 75% (copertura)

**Cosa misura.** Per ogni squadra della lega e per ogni turno, il sistema guarda **tutti i calciatori in rosa** e tiene quelli la cui **squadra vera ha una partita in quella finestra**. Con questi cerca la **migliore formazione possibile**: prova tutti i moduli ammessi e tiene quello che copre più posti. Poi conta quanti degli **11 posti della formazione** riesce a coprire.

**«Titolari» non sono i titolari veri** annunciati mezz'ora prima delle partite. Sono gli **11 posti della formazione del fantacalcio**. Il controllo chiede solo se la squadra vera del calciatore gioca in quel turno, cosa che si sa settimane prima dal calendario ufficiale. Se poi il calciatore va in panchina o non gioca, è il normale rischio del fantacalcio, coperto dalla panchina e dai cambi automatici (fino a 5 subentri).

**La soglia.**
- Il turno è **giocabile** se **ogni** squadra copre almeno il **75%** degli 11 posti, cioè 9 su 11.
- Se anche **una sola** squadra resta sotto, il turno diventa **«Turno saltato»** per tutta la lega: nessuno prende punti. Non succede mai che una squadra prenda 0 mentre le altre giocano.
- La soglia si può cambiare **per lega**, nelle regole, da 50% a 100%. Più bassa vuol dire turni saltati meno spesso, ma qualcuno può giocare con meno titolari. Più alta vuol dire formazioni quasi piene, ma più turni saltati.

**Perché non il 75% della rosa intera.** Servirebbero 27 giocatori su 35 in campo nella stessa finestra. Ogni volta che un campionato della lega non gioca (soste, coppe) quasi tutti i turni salterebbero, e si misurerebbe la cosa sbagliata: in campo ne vanno 11, non 27.

**Esempio.** In un turno gioca solo la Serie A:
- una squadra con 10 giocatori di Serie A, con ruoli che permettono un modulo, copre 10 posti su 11 (91%). Il turno è valido e quella squadra gioca con 10;
- una squadra con 5 giocatori di Serie A copre 5 posti su 11 (45%). Il turno salta per tutti.

## 3. Il calendario dei fantallenatori (scontri diretti)

È una catena:
1. Date delle partite di tutti i campionati della lega, fino a maggio.
2. Finestre dei turni (punto 1).
3. Controllo del 75% su ogni finestra, con le rose di quel momento (punto 2).
4. Le giornate «Squadra A contro Squadra B» vengono assegnate **solo ai turni giocabili**.

**Turni iniziati prima della creazione della lega** (segnaposto «Lega creata dopo questo turno»): non hanno scontri diretti. Dal 24/11 si **omologano da soli** appena tutte le partite del turno sono finite (`FT`/`AET`/`PEN`) e ci sono le statistiche dei giocatori, anche se la lega non ha ancora il calendario. Prima restavano provvisori per sempre e tenevano chiuso il mercato. La notifica dice «Turno concluso… nessuno scontro diretto, la classifica non cambia»; nel registro attività l'omologazione ha `beforeLeagueCreation: true`. Come ogni omologazione, apre il turno dopo solo se la lega è attiva: altrimenti quel turno si apre quando la lega parte. Una lega senza calendario continua invece a dare l'errore `calendar_not_found` per i turni **dopo** la sua creazione: il calendario va generato dall'admin.

**Il calendario non è rigido fino a maggio.** Il sistema ricontrolla da solo i turni futuri a ogni aggiornamento: mercato, svincoli, partite rinviate o spostate.
- Se un turno futuro diventa non giocabile, la sua giornata si sposta o viene tolta. Questo vale solo se non ha ancora risultati: quelli già calcolati non si toccano mai.
- Quando le rose migliorano, i turni futuri diventano più facilmente giocabili.

**Genera calendario con rose non in regola** (dal 22/11, solo sul sito, admin di lega e operatore):
- «Genera calendario» e «Conferma calendario» controllano prima le rose. Se qualcuna non è in regola, la finestra mostra l'elenco, per esempio «Squadra X: Attaccanti 11 su 10», e permette **«Genera comunque»** e **«Conferma comunque»**.
- Restano obbligatori: lega al completo, stagione non conclusa, turni europei disponibili.
- Ogni generazione forzata resta nel registro attività, con i problemi di quel momento.
- **La stagione non parte forzando il calendario.** L'avvio della lega richiede sempre rose in regola (decisione di Rosario del 22/11: nessuna partenza forzata). Appena le rose sono in regola, la lega parte da sola e i turni si aprono.

**Rose non in regola, cosa succede ai giocatori:**
- i giocatori **in esubero** (oltre la quota del ruolo) restano in rosa, ma **non si possono schierare**, né titolari né tra i primi 10 della panchina, finché la rosa non torna in regola. In tribuna vengono tolti senza errore;
- il resto della squadra schiera normalmente;
- una rosa **incompleta**, o con meno di 3 campionati, non può schierare la formazione finché non viene sistemata.

## 4. Ruoli del listone

- **I ruoli ufficiali del listone restano fissi per tutta la stagione**, come nel fantacalcio classico. «Aggiorna listone» (solo l'operatore) aggiunge i calciatori nuovi e aggiorna le squadre, ma **non cambia il ruolo** di chi ce l'ha già.
- Per cambiare i ruoli secondo il fornitore dei dati, nella finestra di «Aggiorna listone» si sceglie **«Aggiorna anche i ruoli dal fornitore»**. Prima di applicare, il sistema mostra un'**anteprima**: chi cambia ruolo, in quali leghe, quante rose andrebbero fuori quota. Poi si conferma o si annulla.
- Il ruolo di un calciatore in una singola lega si cambia con il **ruolo forzato** dell'admin. Vale dal turno successivo all'ultimo iniziato.
- **«Ripristina i ruoli cambiati da un aggiornamento»** (pannello operatore → Listone) ricostruisce i ruoli di prima da un'ora scelta, usando i dati salvati del fornitore. Mostra prima la lista, poi applica.
- Se un calciatore risulta in più squadre attive (es. rientro da un prestito), conta la **squadra attuale**.

## 5. Domande frequenti (testo per i fantallenatori)

Dalla 1.4 queste risposte sono sul sito e nell'app, nella voce di menù «Domande frequenti» subito dopo «Segnala un problema», con in più «Cos'è la regola del 75%?» (dal punto 2): il testo mostrato sta in `packages/contracts/src/faq.ts` e va aggiornato insieme a questo capitolo.

**Regola standard (Rosario, 23/11).** Ogni lega può cambiare la soglia dei titolari (da 50% a 100%), il numero di cambi automatici (da 0 a 5) e i minuti del blocco (da 0 a 60). Dove una risposta cita 9 titolari, 5 cambi o 15 minuti, dice che è la regola standard e rimanda a «Regolamento» nella home della lega, dove dalla 1.4 compaiono anche «Cambi automatici (max)» e «Partite minime per turno».

**Il «?» accanto alle scritte (1.4).** Un piccolo «?» apre la risposta giusta dal basso (sul sito dal computer, in una finestra al centro), con il link «Tutte le domande frequenti» alla pagina con quella risposta aperta:
- accanto a «Stato: Turno saltato» in Turni › Turni europei (uno solo: dal 23/11 non c'è più quello vicino al menù dei turni) → «Perché un turno è «saltato»?»;
- accanto al badge «In esubero» del giocatore in Rosa (sito e app; prima «In attesa», Rosario 23/11) → «Ho un giocatore «in esubero»: cosa faccio?»;
- accanto all'orario del blocco in Formazione → «Quando si blocca la formazione?».

**Perché un turno è «saltato»?** (due motivi, testo approvato da Rosario il 23/11)
Per uno di questi due motivi:
1) in quella finestra si giocano troppo poche partite dei campionati della lega: sotto il minimo della lega, 25 con la regola standard (la tua lega può averne scelto un altro, lo trovi in «Regolamento» alla voce «Partite minime per turno»). Nel turno vedi il numero, per esempio «20 partite eleggibili su 25»;
2) almeno una squadra della lega non avrebbe potuto schierare, con giocatori che giocano davvero, almeno 9 titolari (è la regola standard: la tua lega può averne scelta un'altra, la trovi in «Regolamento»). Succede per esempio durante una sosta di uno dei campionati.
Per non svantaggiare nessuno, il turno non conta per nessuno.

**Se un mio titolare non gioca, prendo 0?**
No: entra un giocatore della tua panchina, nell'ordine che hai scelto e rispettando il modulo, fino a 5 cambi (è la regola standard: la tua lega può averne scelti altri, li trovi in «Regolamento»). È il normale funzionamento del fantacalcio.

**Ho tanti giocatori di campionati diversi: rischio?**
Se in un turno gioca solo un campionato e tu non hai almeno 9 titolari possibili in quel campionato (è la regola standard: la tua lega può averne scelta un'altra, la trovi in «Regolamento»), il turno salta per tutti. Non prendi 0 da solo. Più la rosa è distribuita sui campionati della lega, meno turni saltano.

**Il calendario cambierà?**
Solo le giornate future che diventano non giocabili, per partite rinviate o per cambi di rosa, si spostano. Le giornate con risultati non cambiano mai.

**Perché un mio giocatore ha cambiato ruolo?**
Non dovrebbe più succedere: dal 22/11 i ruoli del listone sono fissi per la stagione. Se l'admin della lega ha forzato un ruolo, il cambio vale dal turno successivo.

**Ho un giocatore «in esubero»: cosa faccio?**
Hai più giocatori di quelli ammessi in quel ruolo. Puoi svincolarne uno o scambiarlo. Finché la rosa non torna in regola, quel giocatore non si può schierare.

**Quando si blocca la formazione?**
Ogni giocatore si blocca poco prima della sua partita, di solito 15 minuti (è la regola standard: la tua lega può averne scelti altri, li trovi in «Regolamento»). Gli altri giocatori si possono ancora cambiare fino alla loro partita.
