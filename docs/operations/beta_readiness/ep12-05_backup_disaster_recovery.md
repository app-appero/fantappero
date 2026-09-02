# EP12-05 — Backup e disaster recovery

## Stato implementazione

**Implementata e validata su `claude/M5` il 2026-08-21.**

- Servizio Compose opzionale `postgres-backup` con esecuzione immediata + intervallo
  configurabile, dump custom-format atomico, tre tentativi, retention 14 giornalieri/8
  settimanali, lock condiviso fra job schedulati/manuali, log strutturati, stato/metriche
  textfile, healthcheck di freshness e webhook opzionale dopo il fallimento definitivo.
- Backup coordinato del volume avatar; Redis è dichiarato ricostruibile e non viene
  incluso nei backup Beta.
- Restore PostgreSQL automatizzato solo su
  `postgres-test/fantappero_restore_ep12`, con guardie non aggirabili dalla configurazione
  Compose, checksum, manifest di schema, constraint e revisione Alembic. Restore avatar
  solo su `tmpfs` vuoto.
- Verifica ripetibile di tutte le tabelle (conteggi + digest), sequence e avvio reale
  dell'API sul DB ripristinato tramite `infra/scripts/dr_restore_drill.sh`.
- RPO Beta 24 h, RTO 2 h, responsabilità, alert, procedura incidente e limiti documentati
  in `docs/operations/backup_disaster_recovery.md`.
- Evidenza del drill reale: `docs/operations/evidence/ep12-05_restore_drill_2026-08-21.md`.
  Esito PASS: backup 6 s, restore 4 s, 60 tabelle/62.455 righe e sequence identiche,
  constraint invalidi 0, restore avatar e readiness API riusciti; verificati anche retry,
  healthcheck, retention e rifiuto del target non allowlisted.

Vincolo operativo residuo: il default locale salva sotto `artifacts/backups`; prima del
pilot `POSTGRES_BACKUP_HOST_PATH` deve puntare a storage indipendente dal disco Postgres,
cifrato e replicato offsite, e il monitor deve notificare il container unhealthy.

| Metadato | Valore |
| --- | --- |
| Card | EP12-05 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | Nessuna dipendenza diretta dalle altre card EP12 (lavoro infra indipendente) |
| Stima originale | 3–5 giorni |

## Obiettivo e scope

Automatizzare i backup e testare il restore; definire RPO/RTO Beta e dimostrare un
restore riuscito, con piano, dati di test, responsabile ed evidenze.

## Stato attuale nel repo (gap)

- **Nessun meccanismo di backup automatizzato** presente: `compose.yaml` definisce
  `postgres` con un volume nominato persistente, ma nessuno script/job di dump
  periodico, nessuna configurazione di retention.
- **Nessun documento RPO/RTO** esiste in `docs/operations/` né altrove.
- Dati da proteggere, in ordine di criticità (dal modello di dominio ricostruito):
  - Postgres: dati transazionali critici (ledger crediti, rose, formazioni, mercato,
    risultati, audit log EP11-03) — priorità massima.
  - Redis: usato per lock distribuito dello scheduler sportivo
    (`backend/src/sports_data/scheduler/locks.py`) e presumibilmente cache/codelivery
    Celery — verificare se contiene stato non ricostruibile da Postgres o solo stato
    effimero/ricomputabile (in tal caso backup Redis può essere a priorità inferiore).
  - Volume `avatar storage` — dati utente non ricostruibili automaticamente.

## Piano d'azione

1. **Definire RPO/RTO Beta** (proposta di struttura; valori concreti da concordare col
   team, non deducibili dal codice):
   - RPO (quanti dati è accettabile perdere) — proposta di partenza: dump giornaliero
     come minimo per la fase Beta, con possibilità di aumentare frequenza se il pilot
     (EP12-07) lo richiede.
   - RTO (quanto tempo per tornare operativi) — da definire in base a dimensione dataset
     Beta (presumibilmente piccola, RTO breve raggiungibile).
2. **Implementare backup automatico Postgres**: script/job `pg_dump` schedulato (Celery
   beat, già presente in `compose.yaml` come servizio `beat`, riusabile per schedulare il
   job invece di introdurre un nuovo scheduler) con output verso storage esterno al
   container (volume dedicato o, se disponibile, storage object esterno — da confermare
   con l'infra disponibile in fase di implementazione).
3. **Definire retention policy** (es. N backup giornalieri + M settimanali), documentata
   e applicata dallo stesso job.
4. **Automatizzare/documentare il backup Redis** se il punto 1 conferma che contiene stato
   non ricostruibile; altrimenti documentare esplicitamente che Redis è ricostruibile da
   Postgres/provider e non richiede backup dedicato in Beta.
5. **Scrivere ed eseguire una procedura di restore testata**: ripristino di un dump su
   un'istanza Postgres pulita (via `docker compose`, riusando il servizio
   `postgres-test` come ambiente di prova), verificando integrità referenziale e coerenza
   applicativa post-restore (smoke test contro l'app puntata al DB ripristinato).
6. **Documentare backup e restore come runbook operativo** in
   `docs/operations/backup_disaster_recovery.md` (nuovo documento, fuori da questa
   cartella di pianificazione — è deliverable dell'implementazione, non del piano),
   riusato poi da EP12-06.

## Tooling proposto

- `pg_dump` / `pg_restore` (già incluso nell'immagine Postgres usata da `compose.yaml`,
  nessuna nuova dipendenza).
- Scheduling: riuso di Celery beat (`beat` già presente in `compose.yaml`) invece di
  introdurre `cron` o altri scheduler, per coerenza con lo stack esistente.

## Dati di test

- Ambiente `postgres-test` (già presente in `compose.yaml`, profilo `test`) come target
  del restore di prova, per non rischiare il DB di sviluppo/pilot durante i test.
- Dataset di dimensione realistica per la fase Beta (non serve dataset di produzione:
  volume simile a quello generato dallo scenario di seed E2E di EP12-01, eventualmente
  moltiplicato).

## Criteri di accettazione (dalla card)

- RPO/RTO Beta definiti; restore dimostrato.
- Evidenze collegate alla card.

## Test minimi richiesti

- Smoke test dell'ambiente e verifica di log, metriche, retry e configurazione del job di
  backup (es. cosa succede se il dump fallisce: retry, alert).
- Test di integrazione: restore completo su ambiente pulito, con verifica applicativa
  post-restore (non solo verifica che il dump SQL sia sintatticamente valido).

## Rischi e domande aperte

- Destinazione di storage dei backup fuori dal container/host locale non è ancora
  definita (nessuna integrazione con storage esterno rilevata nel repo): da chiarire con
  il team se la Beta richiede storage offsite o se un volume locale con retention è
  sufficiente per questa fase.
- I valori numerici di RPO/RTO non sono decidibili unilateralmente in questa
  pianificazione: richiedono conferma esplicita del team/responsabile della card.
