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
  attive (Turni), versione dell'app annunciata (Versione app).

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

## Variabili correlate

| Variabile | Obbligatoria | Descrizione |
| --- | --- | --- |
| `BOOTSTRAP_OPERATOR_EMAIL` | No | Email di un utente già registrato, usata dal comando quando `--email` è omesso. Vedi anche [`configuration_and_secrets.md`](./configuration_and_secrets.md). |

## Debito noto (fuori scope EP11-04a)

- Nessuna audit UI consultabile per le promozioni/revoche (solo log strutturato) — arriverà con EP11-03.
- Nessuna gestione di anomalie/job operatore da `/admin` — EP11-04 resto.
- Nessun hub QA/demo per operatori in ambienti non-prod — EP11-06 (Should, card futura).
