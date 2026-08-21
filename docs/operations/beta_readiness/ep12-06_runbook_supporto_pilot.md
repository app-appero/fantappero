# EP12-06 — Runbook e supporto pilot

## Stato implementazione (branch `claude/M5`)

**Implementazione tecnica e simulazioni completate il 2026-08-21.**

- Cinque procedure uniformi e aderenti agli strumenti reali sono disponibili in
  [Runbook incidenti Beta pilot](../pilot_incident_runbooks.md): dati sportivi mancanti,
  ricalcolo turno omologato, incidente sicurezza, perdita/corruzione dati ed errore di
  mercato.
- Canale, triage, severità, escalation, template e KPI del supporto sono definiti in
  [Processo supporto Beta pilot](../pilot_support_process.md). Ruoli, canali e tempi sono
  proposte esplicitamente da confermare, non SLA già approvati.
- `infra/scripts/verify_pilot_runbooks.sh` ripete i cinque scenari senza modificare il DB
  dev/pilot: 9 test di integrazione su `postgres-test`, più backup/restore reale da
  `postgres-perf` tmpfs a `postgres-test/fantappero_restore_ep12` (target eliminato al
  termine).
- Evidenza versionabile: [simulazioni EP12-06 del 2026-08-21](../evidence/ep12-06_runbook_simulations_2026-08-21.md).

Il perimetro tecnico della card è coperto, ma l'onboarding EP12-07 resta bloccato finché
il team non assegna nominativi/canali, approva i tempi proposti e inserisce nella scheda
dell'ambiente il comando reale di cutover DR. Il repo non offre una revoca immediata di
una singola access session né l'undo di una transazione mercato già applicata: i runbook
documentano il contenimento/tabletop senza aggirare questi limiti con SQL manuale.

| Metadato | Valore |
| --- | --- |
| Card | EP12-06 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | EP12-04 (security review, per le procedure di incidente di sicurezza), EP12-05 (backup/DR, per la procedura di rollback/restore) |
| Stima originale | 3–5 giorni |

## Obiettivo e scope

Documentare incidenti, dati mancanti, ricalcoli e rollback in modo che **un operatore
possa gestire gli incidenti previsti senza intervento improvvisato**, con piano, dati di
test, responsabile ed evidenze.

## Ricognizione iniziale (gap ora coperti)

- `docs/operations/` non aveva un runbook operativo trasversale per incidenti: conteneva
  guide a singole funzionalità/sync (es. `sports_scheduler.md`,
  `sports_data_quality.md`, `admin_operator_bootstrap.md`). Il gap è ora coperto dai due
  documenti EP12-06 collegati sopra.
- Esiste già materiale riusabile come base per i runbook, non da riscrivere:
  - `docs/operations/sports_data_quality.md` — pannello qualità dati (EP04-07), copre già
    "mancanti", "ritardi", "conflitti", "correzioni" con audit su
    `sports_data_sync_retries`: è la base naturale per il runbook "dati mancanti".
  - `docs/operations/observability_baseline.md` — correlation-id, log strutturati,
    metriche, probe `/live`/`/ready`: base per "come diagnosticare un incidente".
  - `backend/src/fantasy_turns/service.py` — logica di ricalcolo/omologazione turni: base
    per il runbook "ricalcolo".
- Il modulo di audit log (EP11-03, da commit `feat: EP11-03/04/05`) è disponibile come
  strumento di indagine per gli operatori durante un incidente — da referenziare nei
  runbook, non da ricostruire.

## Piano d'azione

1. **Individuare gli scenari di incidente coperti dallo scope Beta**, in base ai gap reali
   del dominio (non scenari generici):
   - Dati sportivi mancanti/in ritardo per un turno (già in parte coperto da
     `sports_data_quality.md`: il runbook aggiunge "cosa fa l'operatore step-by-step",
     non la meccanica di sync già documentata).
   - Necessità di ricalcolo di un turno già omologato (correzione punteggio) —
     riferimento a `fantasy_turns/service.py` e ai criteri di omologazione EP07-07.
   - Incidente di sicurezza (accesso non autorizzato, dato esposto) — riferimento a
     EP12-04 e al modulo di audit EP11-03.
   - Perdita/corruzione dati che richiede restore da backup — riferimento diretto alla
     procedura di restore prodotta da EP12-05.
   - Errore di mercato (assegnazione errata, scambio da annullare) — riferimento a
     `backend/src/market` e alle invarianti verificate in EP12-02.
2. **Scrivere un runbook per ciascuno scenario**, formato uniforme (coerente con lo stile
   di `docs/operations/*.md`: tabella metadati, sezione "sintomi", "diagnosi con
   riferimento a log/metriche/audit", "azione correttiva passo-passo", "chi autorizza",
   "come verificare la risoluzione").
3. **Verificare che ogni azione correttiva descritta sia eseguibile con gli strumenti
   già esistenti** (endpoint operatore, script `backend/scripts/` o
   `backend/src/devtools/`, pannello EP11-04) — se manca uno strumento necessario,
   segnalarlo come dipendenza per l'implementazione, non inventare un nuovo tool in fase
   di sola pianificazione.
4. **Definire il canale/processo di supporto pilot**: come un partecipante al pilot
   (EP12-07) segnala un problema, chi lo triagga, SLA di risposta interno (proposta di
   struttura, valori da confermare col team).
5. **Collegare i runbook come evidenza** (i documenti stessi sono la evidenza richiesta
   dalla card, insieme a un eventuale run di prova simulato di un incidente).

## Tooling implementato

Nessuna nuova dipendenza: la card riusa osservabilità, audit e backup esistenti. Il solo
tool aggiunto è uno script Bash di orchestrazione ripetibile,
`infra/scripts/verify_pilot_runbooks.sh`, con target e servizi isolati allowlisted.

## Dati di test

- Ambiente Docker Compose standard per una simulazione "a tavolino" di uno o più scenari
  (es. simulare dati mancanti disattivando temporaneamente la sync e verificare che il
  runbook porti l'operatore alla risoluzione corretta usando solo gli strumenti esistenti).

## Criteri di accettazione (dalla card)

- Un operatore può gestire gli incidenti previsti senza intervento improvvisato.
- Evidenze collegate alla card.

## Test minimi richiesti

- Simulazione end-to-end di almeno uno scenario di incidente per runbook, seguendo
  esclusivamente i passi documentati, per validare che siano sufficienti e corretti.
- Verifica che ogni riferimento a log/metriche/audit nel runbook corrisponda a strumenti
  realmente disponibili (non ipotetici).

## Rischi e decisioni residue

- EP12-04 ed EP12-05 sono implementate e citate: la dipendenza tecnica è risolta.
- Canale, nominativi, copertura e obiettivi di risposta richiedono approvazione
  organizzativa del team.
- Il cutover DR dipende dal deployment reale e deve essere inserito nella scheda ambiente
  prima di EP12-07; il repo automatizza intenzionalmente soltanto restore isolati.
- Access token già emessi non hanno revoca puntuale e il mercato non ha undo per azioni
  terminali. I runbook definiscono contenimento e confini; le eventuali nuove operazioni
  di dominio sono follow-up, non edit manuali sul database.
