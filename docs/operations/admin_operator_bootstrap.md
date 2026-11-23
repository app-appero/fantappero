# Bootstrap del primo operatore (EP11-04a)

Come ottenere il primo `global_operator` sulla piattaforma, in locale e in produzione. Non esiste self-promotion via UI: la registrazione crea sempre `platform_role=user`.

## Come funziona

Un solo comando one-shot, idempotente e sicuro in qualunque ambiente:

```bash
docker compose run --rm api python -m devtools.bootstrap_operator --email you@example.com
```

Oppure, senza `--email`, legge `BOOTSTRAP_OPERATOR_EMAIL` da env:

```bash
docker compose run --rm api python -m devtools.bootstrap_operator
```

Regole:

- **Promuove solo un utente già registrato** (`/accedi/registrati` prima, bootstrap dopo). Non crea account, non gestisce password.
- **No-op se esiste già un operator** (`exit 0`, nessuna modifica): è sicuro lasciare `BOOTSTRAP_OPERATOR_EMAIL` configurata in produzione o rieseguire il comando dopo il primo utilizzo — non farà nulla.
- **Exit 2** se l'email non è impostata (né `--email` né `BOOTSTRAP_OPERATOR_EMAIL`) o se l'utente non è registrato.
- Ogni promozione viene loggata (log JSON strutturato, solo `target_user_id` — nessuna email o altra PII).

## Locale (Docker Compose)

1. Avvia lo stack: `docker compose up -d postgres redis api`
2. Registra un utente normale da `http://localhost:5174/accedi/registrati` e verifica l'email (Mailpit su `http://localhost:8025` se attivo)
3. Promuovilo a operator:

   ```bash
   docker compose run --rm api python -m devtools.bootstrap_operator --email you@example.com
   ```

4. Accedi di nuovo (o aggiorna la sessione): l'utente vede ora `/admin` e la voce «Pannello globale» nell'header.

## Produzione / staging

Stessa identica procedura, una tantum, eseguita come job/comando one-shot verso l'ambiente di destinazione (deploy job, task runner, o accesso diretto al container `api` con le stesse variabili d'ambiente del servizio):

```bash
docker compose run --rm api python -m devtools.bootstrap_operator --email operatore@fantappero.example
```

Non è richiesto alcun flag per "disattivare" il bootstrap dopo il primo operator: il comando è no-op appena esiste un operator, quindi è sicuro lasciarlo nella toolbox operativa e rieseguirlo per errore.

## Operatori successivi

Un operator già autenticato promuove/revoca altri operator da `/admin/utenti` (conferma esplicita richiesta). Non è necessario ripetere il bootstrap — quello serve solo per il primo operator della piattaforma.

## La prima pagina del pannello: «Riepilogo» (release 1.4)

Decisione di Rosario del 22/11 (canvas «Pannello operatore»). `/admin` sul sito e la prima
schermata del pannello nell'app si chiamano «Riepilogo» e non ripetono più il menù:

- in una riga chi sei e l'ambiente; i numeri di utenti, operatori e leghe; le leghe per stato;
- **«Da guardare»**, sei righe che portano ciascuna alla sua voce di menù: richieste tester in
  attesa (Utenti), segnalazioni nuove (Segnalazioni), job spenti e giri finiti con errore nelle
  ultime 24 ore con il motivo (Job automatici), ultimo aggiornamento del listone con data, autore
  e riassunto (Listone), giornate in corso e prossimo blocco delle formazioni fra tutte le leghe
  attive (Turni), versione dell'app annunciata e, dalla 1.4, quanti la hanno su quanti usano
  l'app, es. «4 utenti aggiornati su 12 che usano l'app» (Versione app).

Tutto arriva da `GET /admin/overview` (solo `global:operate`, gli altri 403): ai campi di prima si
aggiungono `leaguesByState` e `watch`. L'esito dei giri dei job sta in `system_job_runs`, scritto
dal worker a fine giro (segnali Celery, `system_jobs/run_recorder.py`): `ok` oppure `failed` con
il motivo; i giri saltati perché il job è spento non si scrivono. Per ogni job restano gli ultimi
50 giri riusciti e gli errori degli ultimi 30 giorni (al massimo 100). L'ultimo aggiornamento del
listone viene da `listone_updates` (vedi [`sports_listone.md`](./sports_listone.md)); il prossimo
blocco si calcola a ogni richiesta, con la regola del countdown «Prossimo blocco».

**«Versione app»** è una voce di menù a sé, dopo «Segnalazioni», sul sito (`/admin/versione-app`)
e nell'app: stesso modulo e stessa chiamata `PUT /admin/app-version` (vedi
[`release_pilota_regole.md`](./release_pilota_regole.md)).

### «Versione app»: notifica e «Chi ha quale versione» (release 1.4)

Decisioni di Rosario del 23/11.

- **Salvare una versione la annuncia davvero.** Con «Salva» parte una notifica «È disponibile la
  versione X dell'app» (nell'elenco delle notifiche e push, categoria «Sistema», evento «Nuova
  versione dell'app» nelle preferenze) con il link di download, agli utenti attivi che **usano
  l'app Android** (qualsiasi versione, anche non nota) **o visitano il sito da un telefono
  Android** e che **non risultano già** su quella versione o una più nuova. Non la ricevono chi
  usa il sito solo da computer o da iPhone (per iOS quando ci sarà l'app) e chi, da quando il
  server registra l'uso, non si è visto né nell'app né sul sito da Android. Con la
  modalità test accesa va solo a chi può usare l'app (tester in lista e operatori). Si rispettano
  le preferenze di ognuno (categoria «Sistema» ed evento, in-app e push) e le ore di silenzio
  della push, come per le altre notifiche. Una sola volta per versionCode: risalvare lo stesso
  versionCode (per esempio per correggere il link o il messaggio) non la rimanda a chi l'ha già
  avuta. Il messaggio dopo «Salva» dice a quanti è partita; se l'invio non riesce la versione
  resta salvata e il messaggio lo dice (salvando di nuovo si riprova).
- **Toccare la notifica** nell'app 1.4 apre il link di download; sul sito la notifica apre il link
  in una nuova scheda. Nelle app più vecchie il tocco apre solo l'app (nell'elenco non fa nulla):
  le 1.2 e 1.3 mostrano poi l'avviso come prima (all'avvio, al più ogni 3 ore), la 1.1 non ha
  l'avviso e il link resta quello del gruppo WhatsApp.
- **L'avviso nell'app** (da 1.4) si ripropone a ogni avvio e a ogni ritorno in primo piano finché
  l'app non è aggiornata; «Più tardi» lo nasconde solo fino al prossimo ingresso.
- **«Chi ha quale versione»**, sotto il modulo (sito e app, `GET /admin/app-version/users`, solo
  `global:operate`): un gruppo per versione, la più nuova in cima, es. «1.4.0 (5): 7 utenti» con
  «aggiornati» se è la versione annunciata o più nuova; per ogni utente soprannome (e nome),
  email e ultima volta visto nell'app. Poi:
  - «Versione non nota (app 1.2 o 1.3)»: app che controllano gli aggiornamenti (`GET /app/version`)
    ma non dicono la versione;
  - «Versione non nota (app 1.1 o precedente)»: app (User-Agent `okhttp/`) che non controllano
    gli aggiornamenti;
  - «Sito da Android (app non installata o non ancora vista)»: chi non si è mai visto nell'app ma
    usa il sito da un telefono Android, con l'ultima visita; ricevono anche loro la notifica (chi
    ha anche l'app sta solo nel gruppo della sua versione);
  - «App mai usata / solo sito», chiuso: nessuna richiesta dall'app né dal sito da Android da
    quando il server registra le versioni (il rilascio 1.4), quindi niente notifica; chi ha usato
    l'app solo prima del rilascio sta qui finché non la riapre.

Come si registra: dalla 1.4 l'app manda la versione in ogni richiesta (`X-App-Version`,
`X-App-Version-Code`, `X-App-Platform`); il backend la scrive in `user_app_usage` (una riga per
utente e piattaforma: versione, da dove si sa, prima e ultima volta), al più una volta ogni
5 minuti per utente (subito se cambia la versione), dopo la risposta e senza mai far fallire la
richiesta. Una fonte meno precisa non cancella una versione esatta. Il sito conta solo da un
telefono Android: una richiesta da un browser con `Android` nello User-Agent (e senza le
intestazioni dell'app) scrive una riga a parte con piattaforma `web-android` (fonte `browser`,
nessuna versione), con lo stesso limite di scritture; il sito da computer o da iPhone e le
richieste fatte impersonando un utente non contano. Le righe spariscono con l'account e
compaiono nell'export dei dati (`appUsage`); l'informativa le cita dalla 2026-11d («Uso
dell'app»).

## Variabili correlate

| Variabile | Obbligatoria | Descrizione |
| --- | --- | --- |
| `BOOTSTRAP_OPERATOR_EMAIL` | No | Email di un utente già registrato, usata dal comando quando `--email` è omesso. Vedi anche [`configuration_and_secrets.md`](./configuration_and_secrets.md). |

## Debito noto (fuori scope EP11-04a)

- Nessuna audit UI consultabile per le promozioni/revoche (solo log strutturato) — arriverà con EP11-03.
- Nessuna gestione di anomalie/job operatore da `/admin` — EP11-04 resto.
- Nessun hub QA/demo per operatori in ambienti non-prod — EP11-06 (Should, card futura).
