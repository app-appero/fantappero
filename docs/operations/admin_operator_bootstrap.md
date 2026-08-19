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

## Variabili correlate

| Variabile | Obbligatoria | Descrizione |
| --- | --- | --- |
| `BOOTSTRAP_OPERATOR_EMAIL` | No | Email di un utente già registrato, usata dal comando quando `--email` è omesso. Vedi anche [`configuration_and_secrets.md`](./configuration_and_secrets.md). |

## Debito noto (fuori scope EP11-04a)

- Nessuna audit UI consultabile per le promozioni/revoche (solo log strutturato) — arriverà con EP11-03.
- Nessuna gestione di anomalie/job operatore da `/admin` — EP11-04 resto.
- Nessun hub QA/demo per operatori in ambienti non-prod — EP11-06 (Should, card futura).
