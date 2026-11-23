# Regole di rilascio durante il pilota

Il tag **`pilota-1`** (e i successivi `pilota-1.x`) punta al commit `6599eb2`: è la versione che i tester stanno usando. Un tag è
un'etichetta fissa su un commit: non si sposta e non cambia anche se `main` va avanti.

## Cosa si può cambiare durante il pilota

- **Sì:** correzioni di bug, testi, grafica che non cambia il comportamento, configurazione.
- **No (salvo decisione esplicita del decision owner):** funzioni nuove, cambi alle regole di
  gioco, cambi allo schema dei dati non necessari alle correzioni. Servono a non cambiare le
  condizioni del pilota mentre lo si sta misurando.

## Numerazione dei tag (decisa da Rosario il 05/11/2026)

- `pilota-1` → prima versione data ai tester.
- `pilota-1.1`, `pilota-1.2`, … → ogni rilascio successivo della stessa fase: le ultime aggiunte
  prima dell'avvio e le correzioni.
- `pilota-2` (poi `pilota-2.1`, …) → si passa al numero successivo solo quando, a pilota avviato,
  si apre un nuovo giro di bug e sistemazioni dopo i riscontri dei tester.

## Come si rilascia una correzione

1. Si corregge il bug su `main` (e allineati `pilota` e il branch di lavoro), con test e CI verde.
2. Si fa il deploy di backend (API e worker), sito e, se serve, si ricostruisce l'app.
3. Si prova la correzione sul sito e sull'app.
4. Si crea un **nuovo tag** sul commit rilasciato, secondo la numerazione sotto
   (da GitHub: Releases → Draft a new release → nuovo tag, target il commit).
5. Si annota in questo file la riga del nuovo tag con cosa cambia.

Il tag si crea **dopo** aver verificato il rilascio, non prima.

### Versione dell'app Android (da pilota-1.2)

- A **ogni** nuovo APK si alzano in `apps/mobile/app.json` sia `expo.version` (nome, es. `1.3.0`)
  sia `expo.android.versionCode` (intero, sempre più alto del precedente). È l'unica fonte: il
  prebuild di `build:android:pilota` li scrive nell'APK e l'app li legge da lì. Con lo stesso
  versionCode Android non installa l'APK come aggiornamento e l'avviso non funziona.
- Usati finora: versionCode `1` per pilota-1 e pilota-1.1 (versione `0.0.0`), `3` per pilota-1.2
  (versione `1.2.0`), `4` per pilota-1.3 (versione `1.3.0`). Il prossimo APK parte da `5`.
- Pubblicato l'APK (Drive, gruppo WhatsApp), l'operatore apre nel pannello operatore la voce di
  menù «Versione app» (dalla 1.4, sul sito `/admin/versione-app` o nell'app; prima era in fondo
  alla prima pagina del sito) e scrive versione, versionCode e link: chi ha un'app più vecchia
  vede l'avviso «È disponibile la versione … dell'app.» con «Scarica» e «Più tardi».
- **Dalla 1.4** (Rosario 23/11) il salvataggio manda anche una notifica (elenco e push) con il
  link a chi usa l'app Android o il sito da un telefono Android e non risulta già su quella
  versione (non a chi usa il sito solo da computer o iPhone), una sola volta per versionCode: si salva quando
  l'APK è davvero scaricabile dal link, non prima. Risalvare lo stesso versionCode per correggere
  link o messaggio non rimanda la notifica. L'avviso nell'app 1.4 torna a ogni ingresso finché
  non si aggiorna. Chi ha aggiornato si vede subito sotto il modulo, in «Chi ha quale versione»
  (vedi [`admin_operator_bootstrap.md`](./admin_operator_bootstrap.md)): le app 1.2 e 1.3 non
  dicono la versione e compaiono come «Versione non nota»; dalla 1.4 in poi la versione è esatta.

## Tornare indietro

Se un rilascio rompe qualcosa, si rifà il deploy del commit del **tag precedente** (es. da
`pilota-1.2` a `pilota-1.1`) su Railway e si ricostruisce l'app se necessaria. Con `pilota-1` non c'è
un precedente: si sospendono gli inviti e si corregge in avanti.
Attenzione: le migrazioni del database non si annullano da sole; una correzione che modifica lo
schema dei dati va valutata prima del rilascio.

## Registro dei tag

| Tag | Commit | Data | Contenuto |
| --- | --- | --- | --- |
| `pilota-1` | `6599eb2` | 05/11/2026 | Prima versione per i tester |
| `pilota-1.1` | `375f2c2` | 20/11/2026 | Ultime aggiunte prima dell'avvio (modalità test, lista nera, eliminazione utente da pannello, operatore protetto) e correzioni QA fino al 20/11: accesso «oppure con email» senza conferma, link che aprono l'app, tema immediato; formazione con cambio modulo che tiene i migliori per ruolo, giocatori usciti dalla rosa tolti dalle formazioni future, regola d'inizio turno (posto vuoto al primo panchinaro dello stesso ruolo, in panchina sale il primo della tribuna), esubero e giocatori senza ruolo che non bloccano la formazione; conferma prima di accettare uno scambio, orari dell'asta in ora italiana, notifiche degli svincolati; stesso ruolo per le quote ovunque, scelta degli omonimi nell'import, inviti, pannello operatore, grafica. APK `fantappero-pilota-1.1.apk` nella cartella Drive «FantApperò – Release pilota». Tag creato da Rosario dal terminale (senza pagina Release su GitHub) |
| `pilota-1.2` | `6a96fe9` | 22/11/2026 | Correzioni QA del 19-21/11 e decisioni del 20-21/11: mercato solo a lega al completo e «Mercato fermo: turno in corso», «Turno saltato», «Svuota formazione», formazione migliore a turno iniziato, inviti in attesa nei conti; listone con filtri Campionato e Squadra e avviso di ruolo al completo; nomi del fornitore riparati (codifica e «&apos;»); rientrati dal prestito di nuovo nel listone; notifiche che aprono la lega giusta; promemoria con l'orario del blocco; informativa 2026-11c accettata anche con email; sito su iPhone come app e ritocchi grafici (Formazione, Rosa e Mercato, parti comuni); avviso di nuova versione nell'app e app numerata 1.2.0; pagina e versione nelle segnalazioni. APK `fantappero-pilota-1.2.apk` (1.2.0, versionCode 3) nella cartella Drive «FantApperò – Release pilota». Tag creato da Rosario dal terminale |
| `pilota-1.3` | `6a50656` | 23/11/2026 | Release 1.3: Valore di mercato in crediti della lega (ultime 2 stagioni + in corso, solo campionati, ruolo ufficiale) e prezzo consigliato che parte dal Valore in aggiunta manuale, buste e svincolati; media stagionale in ogni riga del mercato (verde in corso, rossa «25/26») e «Ordina per media»; carriera nella scheda calciatore (porte inviolate dalla stagione in corso); «Storico stagioni» nel pannello operatore (import una tantum dal fornitore); correzioni della notte 22→23/11 (Rosa › Storico a 390 px, «Elimina lega» nell'app, Fantallenatori senza chiamate da amministratore, notifiche Spareggio sotto Asta, pastiglie del campo); ritocchi grafici del pannello operatore. APK `fantappero-pilota-1.3.apk` (1.3.0, versionCode 4) nella cartella Drive «FantApperò – Release pilota». Tag creato da Rosario il 23/11. Storico 2024/25 del pilota da completare il 24/11 mattina (riserva di quota del fornitore) |
