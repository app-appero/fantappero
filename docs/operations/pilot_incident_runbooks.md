# Runbook incidenti Beta pilot

Procedure operative EP12-06 per i cinque incidenti attesi durante il pilot. I comandi
sono aderenti agli endpoint e agli script presenti nel repository. Dove il prodotto non
offre una correzione sicura, il runbook lo dichiara esplicitamente e vieta modifiche SQL
improvvisate.

## Regole comuni

| Campo | Regola Beta |
| --- | --- |
| Incident commander | ruolo `coordinatore incidente`, nominativo da confermare prima di EP12-07 |
| Esecutore tecnico | operatore globale (`global:operate`) o platform owner, secondo il passo |
| Autorità di dominio | amministratore della lega interessata |
| Evidenza minima | orari UTC, ambiente, impatto, correlation ID, endpoint/status, decisioni e riferimenti audit; mai token, password, dump o PII |
| Sicurezza dati | nessun edit SQL manuale; restore sempre prima su target isolato; nessun test sul DB pilot |

Prima di intervenire:

1. Aprire il ticket incidente nel canale scelto dal processo supporto e assegnare severità.
2. Annotare l'ora UTC e un correlation ID nuovo; inviarlo come `X-Correlation-ID` nelle
   richieste diagnostiche e conservarlo nel ticket.
3. Controllare `GET /live`, `GET /ready` e, dal solo perimetro operativo protetto,
   `GET /metrics`. Le metriche sono process-local con più worker: servono come indizio,
   non come conteggio autorevole aggregato.
4. Conservare solo estratti redatti dei log JSON. Non copiare header `Authorization`,
   chiavi provider, DSN o contenuto personale.
5. Comunicare stato e prossima verifica secondo
   [Processo supporto pilot](./pilot_support_process.md).

Nei frammenti seguenti `API_BASE_URL`, `ACCESS_TOKEN`, `LEAGUE_ID`, `ROUND_ID` e gli
altri ID sono variabili della shell operativa. Acquisire il token con un metodo che non
lo salvi nella history e non usare `set -x`.

## RB-01 — Dati sportivi mancanti o in ritardo

| Metadato | Valore |
| --- | --- |
| Trigger | fixture terminata senza eventi/lineup/statistiche; kickoff scaduto; dato provider in ritardo |
| Autorizza | coordinatore incidente; amministratore lega conferma l'impatto |
| Esegue | operatore globale |
| Strumenti | pannello qualità EP04-07, metriche/log provider, audit `sports_data_sync_retries` |

### Sintomi e diagnosi

- La formazione, i voti o i risultati restano incompleti.
- `sports_data_quality_open_issues` cresce oppure i log riportano
  `sports_data_quality_scan_*` / `sports_data_quality_retry_*`.
- La readiness può restare verde: un gap di contenuto non equivale a indisponibilità del
  processo.

Eseguire uno scan idempotente e leggere le issue aperte:

```bash
curl -fsS -X POST "$API_BASE_URL/sports-data/quality/scan" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -H 'Content-Type: application/json' \
  -d '{}'

curl -fsS "$API_BASE_URL/sports-data/quality/issues?status=open&limit=100" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Correlation-ID: $CORRELATION_ID"
```

Registrare `issue.id`, `code`, `fixtureId`, `fixtureProviderId`, `severity` e
`lastSeenAt`. Non dedurre che una partita sia conclusa dal solo orario: verificare lo
stato provider (`FT`, `AET` o `PEN` per l'omologazione).

### Azione correttiva

1. Se il provider è indisponibile o in rate limit, non martellarlo: verificare i log e
   `provider_rate_limit_remaining`, attendere la finestra di recupero e controllare la
   configurazione della chiave senza stamparne il valore.
2. Per una singola issue con target valido, rilanciare una sola sync auditata:

   ```bash
   curl -fsS -X POST \
     "$API_BASE_URL/sports-data/quality/issues/$ISSUE_ID/retry-sync" \
     -H "Authorization: Bearer $ACCESS_TOKEN" \
     -H "X-Correlation-ID: $CORRELATION_ID"
   ```

3. Conservare `retry.id`, `status`, `counters` ed eventuali `errorCode`; verificare anche
   `GET /sports-data/quality/retries/{retry_id}`. Non correggere direttamente tabelle di
   fixture/eventi.
4. Ripetere lo scan. L'issue deve passare a `resolved`; un nuovo retry fallito richiede
   escalation al platform owner/provider, non un loop manuale senza limite.
5. Se il dato corretto cambia un turno già omologato, proseguire esclusivamente con
   RB-02. Il retry non riapre un turno omologato.

### Verifica e chiusura

- issue risolta dopo nuovo scan;
- retry `ok` con audit disponibile e nessun errore provider successivo;
- dati della fixture leggibili e downstream coerente;
- partecipanti informati dell'eventuale ritardo/correzione.

Riferimento di dettaglio: [Pannello qualità dati sportivi](./sports_data_quality.md).

## RB-02 — Ricalcolo controllato di un turno omologato

| Metadato | Valore |
| --- | --- |
| Trigger | rettifica ufficiale del provider o errore di scoring confermato dopo omologazione |
| Autorizza | amministratore lega + coordinatore incidente |
| Esegue | operatore globale |
| Audit | `fantasy_round_correction_applied`, nuova `fantasy_round_homologated` |

### Sintomi e diagnosi

Confrontare il dettaglio del turno, i risultati persistiti, la classifica e l'audit:

```bash
curl -fsS "$API_BASE_URL/leagues/$LEAGUE_ID/turni/$ROUND_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
curl -fsS "$API_BASE_URL/fantasy-scoring/rounds/$ROUND_ID/risultati" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
curl -fsS "$API_BASE_URL/leagues/$LEAGUE_ID/audit?pageSize=100" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Procedere solo se `homologationStatus=homologated`, la rettifica è verificata e il ticket
contiene motivo e impatto. Un ricalcolo ordinario su un turno omologato viene
correttamente rifiutato con `round_homologated`. I rating di una fixture sono globali:
se la stessa fixture appartiene a turni omologati di più leghe, il guard blocca il
ricalcolo finché ogni turno interessato non è stato identificato e riaperto con
autorizzazione separata. Non esiste un endpoint bulk; l'operatore deve inventariare le
leghe dal pannello admin e verificare i rispettivi dettagli turno.

### Azione correttiva

1. Comunicare che i risultati tornano provvisori. Riaprire con un motivo specifico:

   ```bash
   curl -fsS -X POST "$API_BASE_URL/fantasy-scoring/rounds/$ROUND_ID/correzione" \
     -H "Authorization: Bearer $ACCESS_TOKEN" \
     -H "X-Correlation-ID: $CORRELATION_ID" \
     -H 'Content-Type: application/json' \
     -d '{"reason":"Rettifica ufficiale fixture <id>, riferimento ticket <id>"}'
   ```

   L'esito atteso è `homologationStatus=provisional`; il motivo vuoto è rifiutato.
2. Se necessario, risolvere prima il dato sorgente con RB-01.
3. Ricalcolare i voti per ogni fixture corretta, identificata dal dettaglio turno:

   ```bash
   curl -fsS -X POST "$API_BASE_URL/fantasy-ratings/compute" \
     -H "Authorization: Bearer $ACCESS_TOKEN" \
     -H "X-Correlation-ID: $CORRELATION_ID" \
     -H 'Content-Type: application/json' \
     -d "{\"fixtureId\":\"$FIXTURE_ID\"}"
   ```

4. Ricalcolare nell'ordine formazione effettiva, risultati e classifica:

   ```bash
   curl -fsS -X POST \
     "$API_BASE_URL/fantasy-lineups/rounds/$ROUND_ID/formazione-effettiva" \
     -H "Authorization: Bearer $ACCESS_TOKEN" \
     -H 'Content-Type: application/json' -d '{}'
   curl -fsS -X POST "$API_BASE_URL/fantasy-scoring/rounds/$ROUND_ID/risultati" \
     -H "Authorization: Bearer $ACCESS_TOKEN" \
     -H 'Content-Type: application/json' -d '{}'
   curl -fsS -X POST "$API_BASE_URL/fantasy-scoring/leagues/$LEAGUE_ID/classifica" \
     -H "Authorization: Bearer $ACCESS_TOKEN"
   ```

5. Confrontare risultati/classifica con l'atteso approvato. In caso di dubbio lasciare
   il turno `provisional`; i calcoli sono idempotenti e non va omologato un dato incerto.
6. Omologare di nuovo soltanto quando tutte le fixture non escluse sono terminali:

   ```bash
   curl -fsS -X POST "$API_BASE_URL/fantasy-scoring/rounds/$ROUND_ID/omologa" \
     -H "Authorization: Bearer $ACCESS_TOKEN" \
     -H "X-Correlation-ID: $CORRELATION_ID"
   ```

### Verifica e chiusura

- nuovo risultato e classifica approvati dall'amministratore lega;
- stato nuovamente `homologated` e formula version presente;
- audit contiene una correzione motivata tra le due omologazioni;
- notifiche di correzione/omologazione create senza duplicazioni inattese.

Non esiste un endpoint di rollback della correzione: il rollback sicuro consiste nel
lasciare il turno provvisorio e ripetere la pipeline idempotente con input corretti.

## RB-03 — Accesso non autorizzato o dato esposto

| Metadato | Valore |
| --- | --- |
| Trigger | aumento dinieghi, accesso cross-lega, account/token/provider key compromesso, dato esposto |
| Autorizza | coordinatore incidente; platform owner per rotazioni/redeploy |
| Esegue | operatore globale e platform owner, in coppia per azioni ad ampio impatto |
| Fonti | log correlati, metriche auth/authz, audit lega, EP12-04 |

### Triage e diagnosi

1. Classificare tipo di materiale: dato pubblico/PII, access token, refresh token, account
   operatore, chiave provider o segreto infrastrutturale.
2. Cercare per finestra UTC e correlation/request ID. Usare le metriche
   `authorization_denied_total` e `auth_login_total` come segnali, considerando il limite
   process-local. L'audit `GET /leagues/{league_id}/audit` documenta le mutazioni di lega
   ma non è un log completo dei tentativi di autenticazione.
3. Riprodurre solo su test con un utente senza permessi; non usare il token sospetto.
4. Preservare gli estratti redatti prima di riavviare servizi o ruotare segreti.

### Contenimento

- **Operatore compromesso:** un secondo operatore revoca immediatamente il ruolo con
  `POST /admin/users/{user_id}/revoke`. Il server rilegge il ruolo dal database ad ogni
  richiesta, quindi il token perde `global:operate`; l'ultimo operatore non è revocabile
  per guardia applicativa.
- **Account utente compromesso:** avviare il reset password verificato. Il reset revoca
  tutte le refresh session dell'utente. Gli access token già emessi non hanno una
  denylist e restano validi fino alla scadenza configurata (default 15 minuti).
- **Contenimento immediato globale:** se non è accettabile attendere il TTL, il platform
  owner ruota `JWT_SECRET_KEY` nel secret manager e ricrea l'API. La rotazione invalida
  tutti gli access token, non le refresh session: l'account compromesso deve completare
  anche il reset password prima della riapertura.
- **Chiave provider/DSN esposto:** revocare/ruotare sul provider, aggiornare il secret
  manager e ridistribuire i soli servizi consumatori. Non inserire il nuovo valore nel
  ticket o nei log.
- **Route che espone dati:** limitare temporaneamente la route al reverse proxy oppure,
  se l'esposizione continua e non esiste un controllo più stretto già predisposto,
  fermare l'accesso pubblico fino alla correzione. Il comando dipende dal deployment e
  deve essere eseguito dal platform owner.

### Eradicazione, recupero e verifica

1. Correggere il controllo lato server, aggiungere un test di bypass diretto e rieseguire
   le suite auth/authz/security pertinenti.
2. Verificare che l'utente cross-lega riceva `403` (`league_access_denied`/`forbidden`),
   che l'audit resti leggibile solo agli autorizzati e che `/ready` sia verde.
3. Valutare obblighi di comunicazione/privacy con il responsabile umano; il repository
   non implementa un flusso legale di breach notification.
4. Chiudere solo dopo rotazione/revoca verificata, finestra di accesso ricostruita e
   decisione documentata.

Riferimenti: [Security review EP12-04](./beta_readiness/ep12-04_security_review.md),
[Configurazione e segreti](./configuration_and_secrets.md),
[Osservabilità](./observability_baseline.md).

## RB-04 — Perdita o corruzione dati

| Metadato | Valore |
| --- | --- |
| Trigger | tabelle/righe mancanti, constraint o migrazione corrotti, DB indisponibile non recuperabile in-place |
| Obiettivi | RPO massimo 24 h; RTO massimo 2 h per dataset Beta fino a 5 GiB |
| Autorizza | coordinatore incidente + seconda persona del team per punto di ripristino/switch |
| Esegue | platform owner/on-call |

### Triage

1. Rendere l'applicazione read-only al livello di deployment o sospendere le scritture;
   il repo non contiene un feature flag read-only. Se il deployment non offre il blocco,
   fermare l'API prima di un restore reale.
2. Annotare ultimo istante certamente corretto, entità coinvolte e possibili scritture da
   ricostruire via audit/comunicazioni.
3. Verificare health e log del backup, checksum, manifest, replica offsite e data UTC.
4. Selezionare il più recente backup precedente alla corruzione e far approvare la scelta.
   Un errore singolo di mercato non giustifica normalmente un restore globale: usare RB-05.

### Restore e decisione di switch

Il repository supporta e automatizza **solo** il restore isolato su
`postgres-test/fantappero_restore_ep12` e avatar in staging vuoto:

```bash
docker compose build api
ENV_FILE=infra/local/.env bash infra/scripts/dr_restore_drill.sh
```

Il drill verifica checksum, tutte le tabelle con fingerprint delle righe, sequence,
constraint, archivio avatar e readiness API. Non rimuovere le guardie
`CONFIRM_RESTORE=isolated-test-only` e non cambiare l'allowlist del target.

1. Eseguire il drill con il backup scelto (`RESTORE_BACKUP_FILE`) e conservare il report
   redatto.
2. Confrontare audit e ticket per stimare le operazioni tra backup e incidente da
   ricostruire.
3. Solo dopo verifica e doppia approvazione, il platform owner esegue il cutover secondo
   il deployment reale. **Il repo non conosce il topology/secret manager del pilot e non
   fornisce uno script di restore in-place o cutover produzione.** Il comando di switch
   deve essere aggiunto alla scheda ambiente prima di EP12-07.
4. Ricreare Redis vuoto; riaccodare i job persi e risincronizzare i dati sportivi. Redis
   non è system of record nel perimetro Beta.

### Verifica e rollback

- `/ready` e smoke funzionali verdi sul target ripristinato;
- conteggi/fingerprint/constraint e avatar verificati;
- amministratore lega valida rosa, crediti, formazioni, risultati e mercato;
- monitoraggio rafforzato per almeno un ciclo operativo;
- se la verifica fallisce, non effettuare lo switch (o tornare al vecchio endpoint DB se
  lo switch è già avvenuto e il deployment lo consente) e provare un backup precedente.

Procedura completa: [Backup e disaster recovery](./backup_disaster_recovery.md).

## RB-05 — Errore di mercato

| Metadato | Valore |
| --- | --- |
| Trigger | offerta/proposta errata, assegnazione o scambio contestato, saldo/rosa incoerente |
| Autorizza | amministratore lega; coordinatore incidente per operazioni già applicate |
| Esegue | partecipante per proprie azioni pendenti; amministratore per approval; operatore per indagine |
| Fonti | storico mercato, audit lega, ledger crediti, ownership roster |

### Diagnosi

Bloccare nuove decisioni di mercato a livello organizzativo e raccogliere:

```bash
curl -fsS "$API_BASE_URL/leagues/$LEAGUE_ID/mercato/storico?pageSize=100" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
curl -fsS "$API_BASE_URL/leagues/$LEAGUE_ID/audit?pageSize=100" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Confrontare `proposalId`/`sessionId`, attore, timestamp, squadre, atleti, crediti e stato.
Non basarsi su screenshot. Distinguere tassativamente azione ancora pendente da
transazione già eseguita.

### Azioni supportate prima dell'esecuzione

- offerta propria durante sessione aperta:
  `DELETE /leagues/{league_id}/mercato/{asta|waiver}/sessioni/{session_id}/offerte/{athlete_id}`;
- proposta di scambio propria `pending`:
  `POST /leagues/{league_id}/mercato/scambi/proposte/{proposal_id}/annulla`;
- proposta ricevuta `pending`:
  `POST .../{proposal_id}/rifiuta`;
- scambio `awaiting_approval`:
  `POST .../{proposal_id}/amministrazione/rifiuta` con `market:manage`.

Rileggere proposta/storico e verificare lo stato terminale. Le transizioni sono atomiche:
in concorrenza una sola decisione vince.

### Transazione già eseguita: confine operativo

Non esiste un endpoint di undo per asta risolta, svincolo applicato o scambio eseguito.
Non modificare manualmente roster, ownership interval o ledger: romperebbe le invarianti
e l'audit. Inoltre un restore globale per una sola transazione farebbe perdere azioni
legittime non correlate.

1. Congelare nuove azioni di mercato e preservare storico/audit.
2. Verificare se si tratta di bug tecnico oppure decisione valida ma contestata.
3. Se c'è corruzione sistemica, valutare RB-04 con doppia approvazione.
4. Negli altri casi, il coordinatore registra la decisione prodotto. Una futura
   compensazione deve essere implementata come operazione di dominio atomica e auditata;
   non è disponibile nella Beta corrente. Finché manca, l'incidente resta aperto o viene
   accettato esplicitamente dall'amministratore della lega e dai partecipanti coinvolti.

### Verifica e chiusura

- stato proposta/sessione coerente e non modificabile una seconda volta;
- un solo owner attivo per atleta, rose coerenti e saldo ricostruibile dal ledger;
- storico e audit concordano su attore e risultato;
- decisione e comunicazione ai partecipanti registrate.

## Simulazione ripetibile

La suite EP12-06 esegue i cinque scenari senza toccare il DB dev/pilot:

```bash
ENV_FILE=infra/local/.env.example bash infra/scripts/verify_pilot_runbooks.sh
```

I primi quattro scenari usano `postgres-test` e Redis `tmpfs`; il DR crea un dataset in
`postgres-perf` `tmpfs`, lo salva in un path artifact dedicato e lo ripristina solo in
`postgres-test/fantappero_restore_ep12`. I casi senza strumento di produzione (cutover
DR, revoca immediata di una singola access session, undo mercato terminale) sono tabletop
espliciti: nessuna simulazione aggira quel confine con SQL.
