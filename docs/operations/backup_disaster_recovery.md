# Backup e disaster recovery — Beta

Runbook operativo per EP12-05. Copre PostgreSQL e gli avatar del pilot; Redis è
deliberatamente escluso dal perimetro di backup. Le procedure di restore fornite dal
repo operano solo su `postgres-test` e su uno staging avatar vuoto: non sovrascrivono mai
il database o il volume avatar di sviluppo/pilot.

## Obiettivi Beta e responsabilità

| Obiettivo | Valore Beta | Motivazione e misura |
| --- | --- | --- |
| RPO PostgreSQL | **massimo 24 ore** | Un dump ogni 86.400 s. Il pilot è piccolo e assistito; operazioni successive al dump si ricostruiscono, quando possibile, da audit e comunicazioni del pilot. Un backup manuale è obbligatorio prima di migrazioni o operazioni ad alto rischio. |
| RPO avatar | **massimo 24 ore** | L'archivio avatar è creato nello stesso job e con lo stesso timestamp del dump. Gli avatar sono dati utente non ricostruibili dal database. |
| RTO servizio | **massimo 2 ore** dalla dichiarazione dell'incidente | Budget: 15 min triage/selezione backup, 30 min restore per dataset Beta fino a 5 GiB, 30 min verifiche, 45 min decisione/switch/rollback. Il drill va ripetuto se il dump supera 5 GiB o il restore supera 30 min. |
| Retention | **14 giornalieri + 8 settimanali** | Due settimane di granularità giornaliera e circa due mesi di punti settimanali, con pruning automatico per numero di archivi. Il settimanale è promosso la domenica UTC. |

Owner operativo Beta: **on-call/supporto pilot**. L'owner controlla il job ogni giorno e
guida il drill mensile. Durante un incidente una seconda persona del team approva la
selezione del punto di ripristino e l'eventuale switch. EP12-06 deve assegnare i nomi e i
canali reali prima dell'onboarding delle leghe pilota.

Questi obiettivi sono validi solo se il pilot configura una destinazione indipendente dal
disco di PostgreSQL e una replica offsite. Il default locale `./artifacts/backups` serve a
sviluppo e drill, non soddisfa da solo il requisito di disaster recovery dell'host.

## Cosa viene protetto

### PostgreSQL: backup obbligatorio

PostgreSQL è il system of record per utenti, leghe, rose, ledger crediti, formazioni,
mercato, risultati e audit. `postgres-backup` usa `pg_dump --format=custom`, pubblica il
file solo dopo la validazione con `pg_restore --list` e lo accompagna con:

- checksum SHA-256 del dump e del manifest;
- revisione Alembic e metadati non sensibili dell'archivio;
- stato dell'ultimo successo e metriche textfile senza segreti;
- archivio giornaliero ed eventuale copia settimanale.

Il dump logico è consistente rispetto alla snapshot PostgreSQL presa da `pg_dump`; non è
necessario fermare l'API.

### Avatar: backup obbligatorio con limite noto

Il volume `fantappero_avatar_data` contiene upload non ricostruibili. Il job monta il
volume in sola lettura e crea un `tar.gz` nello stesso ciclo del dump. Il codice applicativo
scrive file piccoli, ma non offre snapshot del filesystem: un upload concorrente può far
fallire `tar`, facendo scattare i retry dell'intero job. Il restore avviene sempre in una
directory vuota di staging; prima dello switch si confrontano i file con gli `avatar_url`
nel database ripristinato.

### Redis: nessun backup Beta

Redis non è un system of record in questo stack:

- DB 0 è broker Celery, rate limit e lock scheduler con TTL;
- DB 1 è result backend Celery;
- i dati autorevoli restano in PostgreSQL o sono risincronizzabili dal provider.

In caso di recovery Redis viene ricreato vuoto. Job in volo possono andare persi e vanno
riaccodati dopo la verifica di PostgreSQL; lock e rate limit ripartono da zero. L'AOF
locale aiuta un riavvio ordinario ma non è considerato un backup DR. Questa decisione va
rivista se in Redis viene introdotto stato utente non ricostruibile.

## Architettura e scheduling

È stato scelto un servizio Compose dedicato invece di Celery beat. `pg_dump` è un processo
infrastrutturale, non un task di dominio: il container `postgres:16-alpine` possiede già i
client compatibili, monta il target di backup e gli avatar senza ampliare l'immagine o i
permessi del worker. Un loop minimale esegue il job all'avvio e poi ogni
`BACKUP_INTERVAL_SECONDS`. Un `flock` sullo storage condiviso impedisce la sovrapposizione
fra scheduler e backup manuali eseguiti da container distinti. Le esecuzioni aggiuntive
della domenica non consumano la retention: viene promosso al massimo un set settimanale
per data UTC.

Configurazione rilevante in `infra/local/.env` (i default sono nell'`.env.example`):

```dotenv
POSTGRES_BACKUP_HOST_PATH=/percorso/montato-indipendente/fantappero
BACKUP_INTERVAL_SECONDS=86400
BACKUP_MAX_AGE_SECONDS=93600
BACKUP_MAX_ATTEMPTS=3
BACKUP_RETRY_DELAY_SECONDS=30
BACKUP_DAILY_RETENTION_COUNT=14
BACKUP_WEEKLY_RETENTION_COUNT=8
BACKUP_WEEKLY_DAY_UTC=7
BACKUP_ALERT_WEBHOOK_URL=https://endpoint-operativo-esempio.invalid/hooks/...
```

`POSTGRES_BACKUP_HOST_PATH` deve essere accessibile solo all'account operativo, cifrato a
riposo dal provider/storage e replicato offsite. Password PostgreSQL e webhook restano in
secret manager o env protetto, mai nel repository. Gli script impostano `umask 077`.

Avvio continuo del job:

```bash
docker compose --env-file infra/local/.env --profile backup up -d postgres-backup
docker compose --env-file infra/local/.env --profile backup logs -f postgres-backup
# equivalenti: make backup-service / make backup-logs
```

Backup manuale prima di una modifica rischiosa:

```bash
docker compose --env-file infra/local/.env --profile backup run --rm \
  --entrypoint /bin/sh postgres-backup /scripts/backup_postgres.sh
# equivalente: make backup
```

Da Git Bash su Windows anteporre `MSYS_NO_PATHCONV=1` al comando Docker; il target
`make backup` lo imposta già per evitare la conversione dei path del container.

Non copiare nei ticket dump, avatar, checksum contenenti nomi file sensibili o output con
credenziali. Sono adatti come evidenza i log strutturati redatti e il report del drill.

## Osservabilità, retry e alert

Ogni tentativo scrive log `key=value` su stdout con evento, durata e dimensioni, senza
stampare password o URL del webhook. Dopo un fallimento il job riprova 3 volte con 30
secondi di intervallo; dopo l'ultimo tentativo:

1. salva `state/last_failure.env`;
2. invia un POST al webhook opzionale;
3. continua il loop, così il ciclo successivo può recuperare;
4. resta unhealthy finché non esiste un successo abbastanza recente.

Il healthcheck legge `state/last_success.env` e diventa unhealthy oltre 93.600 secondi
(24 h + 2 h di tolleranza). Docker Compose non inoltra alert da solo: il monitor del pilot
deve notificare sia `container unhealthy` sia `event=backup_failed`. Il webhook è una
seconda via semplice nei limiti dello stack. `state/backup.prom` espone quattro gauge in
formato Prometheus textfile per una futura integrazione; non esiste ancora uno scraper nel
repo.

Controllo giornaliero dell'owner:

```bash
docker compose --env-file infra/local/.env --profile backup ps postgres-backup
docker compose --env-file infra/local/.env --profile backup logs --since 26h postgres-backup
```

Esito atteso: servizio `healthy`, almeno un `event=backup_succeeded`, nessun
`event=backup_failed` successivo. Verificare inoltre che la replica offsite abbia ricevuto
i nuovi file `.dump`, `.tar.gz`, `.meta` e `.sha256`.

## Drill di restore sicuro e ripetibile

Prerequisiti:

- Docker Compose v2, `curl` e Git Bash/WSL su Windows;
- immagine backend aggiornata (`docker compose build api` dopo modifiche agli script);
- database locale migrato e dataset significativo. Il seed/scenario E2E di EP12-01 è la
  base consigliata; il verificatore rifiuta evidenze con meno di 100 righe complessive;
- nessuna scrittura/test E2E concorrente durante il confronto post-restore. Il dump resta
  MVCC-consistente anche con traffico, ma il confronto sorgente/restore fotografa due
  istanti diversi e fallirebbe correttamente se la sorgente cambiasse nel frattempo.

Comando unico:

```bash
docker compose build api
make dr-restore-test
# senza make, da Git Bash:
ENV_FILE=infra/local/.env.example bash infra/scripts/dr_restore_drill.sh
```

Il drill esegue, nell'ordine:

1. backup nuovo del database locale e del volume avatar;
2. checksum e validazione dell'archivio;
3. `drop/create/pg_restore` **solo** su
   `postgres-test/fantappero_restore_ep12`;
4. confronto sorgente/restore per tutte le tabelle tramite conteggio e digest delle righe,
   confronto delle sequence e controllo dei constraint;
5. restore avatar in un `tmpfs` vuoto e controllo dei path dell'archivio;
6. avvio di `api-restore-test` sulla porta 8003, con verifica `/ready` e `/`.

Le guardie richiedono token di conferma, host allowlisted, database con prefisso
`fantappero_restore_`, archivio dentro `/backups` e target avatar sotto `/restore`. Il DB
`fantappero`, `fantappero_test` e il volume avatar live non sono target possibili dei
servizi Compose di restore.

Per ispezionare manualmente il DB ripristinato:

```bash
docker compose --profile backup-test exec postgres-test \
  psql -U fantappero -d fantappero_restore_ep12
```

Per rimuovere solo il database isolato dopo il drill (mai usare contro altri host/DB):

```bash
docker compose --profile backup-test exec postgres-test \
  dropdb -U fantappero --if-exists --force fantappero_restore_ep12
```

## Procedura durante un incidente reale

1. Dichiarare l'incidente, nominare incident commander e secondo approvatore; sospendere
   scritture API/worker/beat conservando log e volumi.
2. Stabilire la causa. Se il problema è applicativo e il DB è integro, preferire rollback
   del deploy: il restore comporta perdita fino all'RPO.
3. Dalla copia offsite scegliere l'ultimo set completo antecedente al guasto. Verificare
   SHA-256 di payload e manifest; registrare timestamp, revisione Alembic e motivazione.
4. Riprodurre anzitutto il restore con il profilo `backup-test`. Se il dump supera 5 GiB,
   misurare la durata prima di promettere l'RTO.
5. Provisionare una **nuova istanza/database vuoto di recovery**. Non usare `pg_restore`
   sul database pilot esistente. Il comando di restore di produzione è responsabilità
   dell'infrastruttura e richiede approvazione a due persone; il repo fornisce
   intenzionalmente solo l'automazione isolata di prova.
6. Ripristinare gli avatar in un nuovo volume, verificare checksum, conteggio e riferimenti
   DB. Creare Redis vuoto; non importare l'AOF precedente.
7. Avviare una sola API di verifica sul nuovo DB: `/live`, `/ready`, login di un account
   test, apertura lega/rosa/formazione/risultato/mercato e controllo ledger/audit.
8. Solo dopo i controlli, spostare traffico/secret al nuovo ambiente. Riabilitare worker e
   beat dopo l'API; riaccodare i job idempotenti necessari.
9. Osservare errori, conteggi e operazioni critiche per almeno 30 minuti. In caso di esito
   negativo, tornare all'ambiente precedente in sola lettura e scegliere un dump diverso;
   non restaurare ripetutamente sopra lo stesso target.
10. Registrare RPO effettivo, RTO effettivo, backup scelto, approvatori e follow-up senza
    allegare dati o segreti.

## Evidenza del drill EP12-05

L'evidenza versionabile è in
`docs/operations/evidence/ep12-05_restore_drill_2026-08-21.md`. Per ogni drill successivo
creare un report analogo con output sintetico e redatto. I dump reali restano sotto il
path gitignored `artifacts/` o nello storage operativo.

## Limiti e trigger di revisione

- Il repo non configura né acquista storage offsite: è un gate operativo del pilot.
- I dump non hanno cifratura applicativa propria; si richiedono volume cifrato, trasporto
  cifrato e ACL del provider. Aggiungere cifratura client-side prima di usare storage non
  fidato.
- Non è disponibile point-in-time recovery/WAL archiving; se RPO 24 h non è più
  accettabile, introdurre backup gestiti/PITR e rifare il drill.
- Il tar avatar non è una snapshot atomica con PostgreSQL. Migrare gli upload a object
  storage versionato quando volume e concorrenza crescono.
- Rivalutare frequenza, RPO/RTO e retention dopo 5 GiB, oltre il pilot assistito o dopo un
  drill che impiega più di 30 minuti per il restore.
