# Informativa privacy — pilota FantApperò

**Stato: bozza, in attesa di approvazione del privacy contact.** Chiuderà F2 solo dopo
che il privacy contact (oggi Rosario Trotta — trottarosario@gmail.com, vedi
`beta_pilot_gate.md`) legge, eventualmente corregge e approva esplicitamente questo
testo — un'automazione non può sostituire questo passo, può solo prepararlo.

Testo minimale, pensato per un pilota piccolo tra conoscenti (non un lancio
commerciale). Se il pilota crescerà o diventerà pubblico, questo testo andrà rivisto
(idealmente con una consulenza legale) prima di quel momento.

## Testo proposto (da mostrare ai tester prima dell'iscrizione)

> **FantApperò — pilota, cosa devi sapere prima di iscriverti**
>
> FantApperò è un'applicazione di fantacalcio in fase di test (pilota). Partecipando
> accetti che il progetto è ancora in sviluppo: possono esserci bug, interruzioni o,
> in casi eccezionali, perdita di dati non recuperabile.
>
> **Cosa raccogliamo**: la tua email, una password (mai salvata in chiaro: viene
> trasformata con un algoritmo di cifratura — Argon2 — che nessuno, nemmeno chi
> gestisce il progetto, può invertire per risalire alla password originale), il nome
> che scegli di mostrare agli altri partecipanti, e i dati di gioco che generi usando
> l'app (leghe a cui partecipi, la tua rosa, le formazioni schierate, i risultati, gli
> scambi di mercato).
>
> **Perché li raccogliamo**: servono esclusivamente a far funzionare il gioco
> (crearti un account, farti entrare nelle leghe, calcolare punteggi e classifiche).
> Non vendiamo né condividiamo i tuoi dati con terzi, non li usiamo per pubblicità.
>
> **Per quanto tempo li teniamo**: finché il tuo account esiste. Puoi chiedere la
> cancellazione in qualsiasi momento (vedi sotto).
>
> **I tuoi diritti, e come esercitarli da solo**: l'app include già due funzioni
> self-service, raggiungibili dal tuo profilo:
> - **Scaricare una copia di tutti i tuoi dati** in un file leggibile, in qualsiasi
>   momento.
> - **Cancellare il tuo account**: l'email viene sostituita con un valore anonimo, la
>   password invalidata, il profilo e l'avatar rimossi, tutte le sessioni attive
>   chiuse. Il nome che avevi scelto resta visibile solo nella classifica storica
>   delle leghe a cui hai partecipato (così i compagni di lega non perdono la storia
>   della stagione), ma scollegato dalla tua identità reale.
>
> Per qualsiasi domanda, richiesta, o per segnalare un problema, scrivi a
> **trottarosario@gmail.com**.
>
> **Ticket e segnalazioni**: se ci scrivi per un problema, non inviare mai la tua
> password o codici di accesso — non ne abbiamo mai bisogno per aiutarti.
>
> **Età minima**: questo pilota non è aperto a persone minorenni.

## Decisioni collegate (F2)

- **Minorenni**: esclusi da questo primo pilota, come da proposta del piano — nessuna
  verifica automatica dell'età nell'app, è una regola di ammissione manuale applicata
  dal pilot coordinator in fase di selezione dei partecipanti.
- **Archivio richieste/ticket**: la casella email personale del privacy contact
  (`trottarosario@gmail.com`) funge anche da archivio per ora, coerente con la scala
  di un pilota piccolo — non è nel repository di codice, è già un sistema ad accesso
  ristretto (solo il proprietario della casella).

## Collegamento con F3 (processo di supporto)

Questo testo è coerente con `pilot_support_process.md`: stesso indirizzo email come
canale segnalazioni, stesso divieto esplicito di inviare password/token nei ticket.
