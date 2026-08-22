# EP12-05 — Evidenza restore drill 2026-08-21

## Esito

**PASS** sul branch `claude/M5`. Drill eseguito il
2026-08-21 in ambiente locale Docker Desktop, con PostgreSQL 16 Alpine e Docker Engine
29.6.2. Nessun dump, avatar, password o URL di alert è versionato in questo report.

Comando ripetibile finale:

```bash
docker compose build api
ENV_FILE=infra/local/.env.example bash infra/scripts/dr_restore_drill.sh
```

Il wrapper è terminato con exit code 0 e messaggio:

```text
DR drill: PASS (database fingerprints, constraints, avatars and API readiness)
```

## Dataset e risultati

- Sorgente: database locale popolato dagli scenari E2E/integrazione della Beta.
- Dimensione database riportata da PostgreSQL prima del drill: 45 MiB.
- Backup custom format: 8.993.432 byte, completato al primo tentativo in 6 secondi.
- Archivio avatar: 33.815 byte; 1 file ripristinato in staging `tmpfs`.
- Restore PostgreSQL isolato: 4 secondi su
  `postgres-test/fantappero_restore_ep12`.
- Revisione Alembic: una sola riga e valore uguale al manifest del backup.
- Constraint pubblici non validati: 0.
- Tabelle pubbliche confrontate: 60.
- Righe complessive confrontate: 62.455.
- Digest di tutte le righe: uguali tra sorgente e restore.
- Stato delle sequence: uguale tra sorgente e restore.
- Tabelle applicative campione: 67 utenti, 43 leghe, 77 fantasy team, 1.414 movimenti
  ledger, 29 formazioni inviate.
- API sul database ripristinato: `/ready` ha riportato PostgreSQL e Redis `ok`; `/` ha
  riportato `fantappero-api` / `ok`.

Output sintetico del verificatore:

```json
{"data_fingerprints_match":true,"invalid_constraints":0,"key_table_rows":{"credit_ledger_entries":1414,"fantasy_teams":77,"leagues":43,"lineup_submissions":29,"users":67},"sequence_fingerprint_match":true,"status":"ok","table_count":60,"total_rows":62455}
```

## Verifiche di failure mode e retention

Retry: esecuzione controllata con host PostgreSQL inesistente,
`BACKUP_MAX_ATTEMPTS=2`, timeout 1 secondo e delay 1 secondo. Sono comparsi due
`event=backup_attempt_failed`, poi `event=backup_failed`; exit code non zero e
`state/last_failure.env` creato. Il healthcheck ha restituito non zero dopo il fallimento;
un backup successivo ha rimosso il failure state e il healthcheck è tornato a exit 0.

Health: avviato `postgres-backup` come scheduler; backup iniziale riuscito in 5 secondi,
seguito da `event=backup_scheduler_sleep` (il ciclo sottrae la durata del job alle 24 ore,
evitando drift dello start). Il controllo manuale e lo stato
Docker hanno riportato `healthy`, failing streak 0.

Retention: esecuzione controllata con retention giornaliera 2, settimanale 1 e giorno
settimanale impostato al giorno del drill. Il job ha promosso un set settimanale e potato
due set giornalieri completi (dump/avatar più manifest e checksum). Sono rimasti due dump
giornalieri e un dump settimanale. Anche il restore esplicito del dump settimanale è
riuscito con manifest di schema corrispondente.

Guardia distruttiva: tentativo controllato con `RESTORE_TARGET_HOST=postgres` e database
`fantappero`; il container ha terminato prima di qualsiasi `dropdb` con
`event=restore_refused reason=host_not_allowlisted`. Il conteggio sorgente è rimasto
invariato.

Durante il drill non erano in corso scritture applicative concorrenti: ciò rende
significativo il confronto digest tra la snapshot del dump e la sorgente corrente.

## Riesecuzione dopo review indipendente

La review finale ha spostato il lock da `/tmp` allo storage condiviso, ha impedito che
più esecuzioni nella stessa domenica consumino gli otto slot settimanali e ha esteso il
fingerprint delle sequence a `last_value` **e** `is_called`.

Sulla versione risultante il drill completo è stato rieseguito con exit code 0 in circa
23 secondi: backup 5 secondi, restore 4 secondi, 60 tabelle/62.455 righe, sequence,
constraint, avatar e API nuovamente PASS. Un test concorrente con due container distinti
ha ottenuto `event=backup_already_running` ed exit code 75 nel secondo container. Due
backup manuali aggiuntivi nello stesso giorno UTC hanno lasciato un solo dump e un solo
archivio avatar nel set settimanale.

## Anomalia rilevata e corretta

Il primo lancio del wrapper da Git Bash su Windows ha convertito `/bin/sh` in un path
Windows e Docker ha rifiutato l'entrypoint prima di avviare il job. Il wrapper ora imposta
`MSYS_NO_PATHCONV=1` quando `OSTYPE` è `msys`; il rilancio completo successivo è PASS.
Questo non ha coinvolto né modificato alcun database.

## Limiti dell'evidenza

- Tempi misurati su dataset locale da 45 MiB, non su storage offsite o dataset da 5 GiB.
- Il webhook non è stato chiamato perché non è disponibile un endpoint operativo nel
  repo; è stata verificata la creazione dello stato di fallimento e la transizione health.
- Il default locale `artifacts/backups` condivide l'host Docker: prima del pilot deve
  essere sostituito con storage indipendente, cifrato e replicato offsite.
- Lo switch di traffico su una nuova istanza di produzione richiede infrastruttura e
  approvazione umana; il repo automatizza intenzionalmente solo il restore isolato.
