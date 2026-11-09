# Informativa privacy — pilota FantApperò

**Stato: v. 2026-11b APPROVATA dal privacy contact (Rosario Trotta) il 09/11/2026.** Contatto
per le richieste: info@fantappero.it. La versione precedente (2026-11, approvata il 04/11/2026)
indicava info@globetrotta.it come contatto, sostituito da info@fantappero.it dopo l'attivazione
del dominio proprio. La versione prima ancora (2026-01, approvata il 28/09/2026) parlava di
email e password e non copriva accesso con Google, segnalazioni con allegati e notifiche.
Testo minimale, pensato per un pilota piccolo tra conoscenti (non un lancio commerciale).
Se il pilota crescerà o diventerà pubblico va rivisto, idealmente con una consulenza legale.

Il testo qui sotto è la fonte unica: è mostrato in app e sul web alla pagina `/privacy`
(contenuto in `packages/contracts/src/privacyNotice.ts`). Cambiandolo si incrementa
`PROFILE_POLICY_VERSION`, così a tutti viene richiesto di accettare di nuovo.

## Testo

> **FantApperò — pilota: cosa devi sapere prima di usarla**
>
> FantApperò è un'applicazione di fantacalcio in fase di test (pilota). Usandola accetti che
> il progetto è ancora in sviluppo: possono esserci bug, interruzioni o, in casi eccezionali,
> perdita di dati non recuperabile.
>
> **Chi tratta i dati**: il progetto FantApperò, gestito da Rosario Trotta
> (info@fantappero.it), che è anche il tuo contatto per qualsiasi richiesta.
>
> **Cosa raccogliamo**
> - *Account*: l'indirizzo email e il nome del tuo account Google (accedi con Google; non
>   riceviamo né salviamo la tua password Google). Il nome o soprannome che scegli di mostrare
>   agli altri partecipanti e l'eventuale foto profilo che carichi.
> - *Dati di gioco*: leghe a cui partecipi, rosa, formazioni, risultati, scambi di mercato.
> - *Segnalazioni*: se usi «Segnala un problema», il testo che scrivi, le immagini o i video
>   che alleghi, la schermata da cui scrivi e informazioni tecniche (tipo di dispositivo,
>   sistema, versione dell'app). Gli allegati sono visibili solo a chi gestisce il progetto.
> - *Notifiche*: se le attivi nell'app Android, un identificativo del dispositivo per inviarti
>   le notifiche e le tue preferenze di notifica.
>
> **Perché li raccogliamo**: solo per far funzionare il gioco (crearti l'account, farti entrare
> nelle leghe, calcolare punteggi e classifiche, avvisarti di eventi di gioco) e per capire e
> correggere i problemi che ci segnali. Non vendiamo né cediamo i tuoi dati, non facciamo
> pubblicità né profilazione. Per l'invio delle email e l'hosting usiamo fornitori tecnici
> (hosting dell'app e del database, servizio di posta, servizio di notifiche) che trattano i
> dati solo per conto del progetto.
>
> **Per quanto tempo**: finché il tuo account esiste. Le segnalazioni si cancellano insieme
> all'account o su tua richiesta.
>
> **I tuoi diritti**
> - *Chiedere una copia di tutti i tuoi dati* (comprese le segnalazioni) scrivendo a info@fantappero.it.
> - *Cancellare il tuo account*: l'email viene sostituita con un valore anonimo, profilo,
>   avatar, segnalazioni e relativi file vengono eliminati, le sessioni chiuse. Il nome che
>   avevi scelto resta solo nelle classifiche storiche delle leghe (così i compagni non perdono
>   la storia della stagione), scollegato dalla tua identità.
>
> Per qualsiasi domanda o richiesta scrivi a **info@fantappero.it**. Non inviare mai
> password o codici di accesso: non ne abbiamo bisogno per aiutarti.
>
> **Età minima**: il pilota non è aperto a persone minorenni.

## Decisioni collegate

- **Minorenni**: esclusi dal pilota; nessuna verifica automatica dell'età, regola di
  ammissione manuale applicata in fase di selezione dei partecipanti.
- **Archivio richieste/ticket**: la casella `info@fantappero.it` funge anche da archivio.
- **Consenso**: l'accesso con Google vale come accettazione (frase con link sotto il tasto); il server salva versione e data al login e il profilo le mostra con il link all'informativa. A ogni nuova versione (`PROFILE_POLICY_VERSION`) l'accettazione si registra al prossimo accesso.
- Coerente con `pilot_support_process.md` (stesso canale, divieto di inviare password/token).
