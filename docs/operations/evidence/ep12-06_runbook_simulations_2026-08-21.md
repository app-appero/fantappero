# Evidenza EP12-06 — simulazioni runbook

| Campo | Valore |
| --- | --- |
| Data UTC | 2026-08-21 |
| Branch | `claude/M5` |
| Comando | `ENV_FILE=infra/local/.env.example bash infra/scripts/verify_pilot_runbooks.sh` |
| Esito | PASS, cinque scenari |
| Dati | fixture repository e dataset sintetici; nessun dato pilot |

## Isolamento verificato

- I test di dominio hanno usato esclusivamente
  `postgres-test/fantappero_test` e `redis-perf` su `tmpfs`.
- La prova DR ha creato un source dataset su
  `postgres-perf/fantappero_performance` (`tmpfs`) con il seed EP12-03 derivato da
  EP12-01; il backup è stato scritto in un path artifact univoco ignorato da Git.
- Il restore è avvenuto solo su
  `postgres-test/fantappero_restore_ep12`; avatar ripristinati in staging `tmpfs` vuoto.
- Al termine lo script ha eliminato il solo database `fantappero_restore_ep12` e rimosso
  i servizi performance/restore allowlisted. `postgres-test` è rimasto attivo; nessun
  servizio o database dev/pilot è stato fermato o modificato.

## Risultati per runbook

### RB-01 — Dati sportivi mancanti

Due test PASS (14,95 s): scan rileva il gap ed è idempotente; retry offline auditato
risincronizza la fixture, è idempotente e risolve l'issue. Copre la sequenza
scan -> issue -> retry -> nuovo scan descritta dal runbook senza chiamare il provider.

### RB-02 — Turno omologato

Un test PASS (12,71 s): l'omologazione blocca ratings, formazione effettiva e risultati;
la correzione senza motivo è rifiutata; una correzione motivata riapre il turno, consente
l'intera pipeline, aggiorna la classifica e permette una nuova omologazione. Verificati
gli eventi audit di entrambe le transizioni.

### RB-03 — Incidente sicurezza

Quattro test PASS (25,90 s): accesso cross-lega e pannello amministrativo senza ruolo
ricevono 403; l'amministratore legge l'audit della propria lega; un estraneo non può
leggerlo. La risposta organizzativa, la rotazione di segreti e la notifica privacy sono
state validate come tabletop perché non esiste né deve esistere un provider/deployment
reale nella suite.

Limite verificato a codice: il reset password revoca tutte le refresh session, mentre un
access token già emesso non ha denylist e dura fino al TTL (default 15 minuti). Per
contenimento immediato servono reset dell'account e, se l'impatto lo richiede, rotazione
globale del JWT/redeploy autorizzati.

### RB-04 — Perdita/corruzione dati

Backup e restore reali PASS su dataset isolato:

- backup PostgreSQL: 291.392 byte, un tentativo, durata riportata 0 s;
- restore: 3 s, revisione Alembic corrispondente, constraint invalidi 0;
- verifica: 59 tabelle, 1.029 righe, fingerprint dati e sequence identici;
- righe chiave: 2 utenti, 2 leghe, 4 squadre, 144 movimenti ledger, 4 formazioni;
- archivio avatar checksum valido e restore in staging riuscito (0 file nel dataset
  sintetico);
- API sul database ripristinato: `GET /ready` 200 `status=ok`.

Queste misure provano il percorso tecnico locale, non RPO/RTO end-to-end: storage
offsite, selezione/approvazione e cutover del deployment pilot restano da esercitare.

### RB-05 — Errore mercato

Due test PASS (26,77 s): due cancellazioni concorrenti di una proposta pendente producono
una sola transizione; uno scambio accettato muove atleti e crediti atomicamente e lascia
ownership/ledger coerenti.

Il caso di transazione terminale errata è tabletop verificabile: router e servizi non
espongono un'operazione di undo. Il runbook vieta edit SQL/restore globale improvvisato e
richiede decisione di dominio o una futura compensazione atomica e auditata.

## Controlli statici

- `bash -n infra/scripts/verify_pilot_runbooks.sh`: PASS.
- `docker compose --env-file infra/local/.env.example config --quiet`: PASS.
- `git diff --check`: PASS prima delle simulazioni; ripetuto nel controllo finale.

Le suite security/market hanno emesso warning Pydantic già presenti su metadata `alias`;
nessun warning ha modificato l'esito dei test. Non sono state eseguite chiamate esterne,
rotazioni reali, restore in-place o comunicazioni a utenti.
