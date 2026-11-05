# Regole di rilascio durante il pilota

Il tag **`pilota-1`** punta al commit `6599eb2`: è la versione che i tester stanno usando. Un tag è
un'etichetta fissa su un commit: non si sposta e non cambia anche se `main` va avanti.

## Cosa si può cambiare durante il pilota

- **Sì:** correzioni di bug, testi, grafica che non cambia il comportamento, configurazione.
- **No (salvo decisione esplicita del decision owner):** funzioni nuove, cambi alle regole di
  gioco, cambi allo schema dei dati non necessari alle correzioni. Servono a non cambiare le
  condizioni del pilota mentre lo si sta misurando.

## Come si rilascia una correzione

1. Si corregge il bug su `main` (e allineati `pilota` e il branch di lavoro), con test e CI verde.
2. Si fa il deploy di backend (API e worker), sito e, se serve, si ricostruisce l'app.
3. Si prova la correzione sul sito e sull'app.
4. Si crea un **nuovo tag** sul commit rilasciato: `pilota-2`, poi `pilota-3`, …
   (da GitHub: Releases → Draft a new release → nuovo tag, target il commit).
5. Si annota in questo file la riga del nuovo tag con cosa cambia.

Il tag si crea **dopo** aver verificato il rilascio, non prima.

## Tornare indietro

Se un rilascio rompe qualcosa, si rifà il deploy del commit del **tag precedente** (es. da
`pilota-2` a `pilota-1`) su Railway e si ricostruisce l'app se necessaria. Con `pilota-1` non c'è
un precedente: si sospendono gli inviti e si corregge in avanti.
Attenzione: le migrazioni del database non si annullano da sole; una correzione che modifica lo
schema dei dati va valutata prima del rilascio.

## Registro dei tag

| Tag | Commit | Data | Contenuto |
| --- | --- | --- | --- |
| `pilota-1` | `6599eb2` | 05/11/2026 | Prima versione per i tester |
