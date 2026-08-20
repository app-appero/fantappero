# EP12-06 — Runbook e supporto pilot

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

## Stato attuale nel repo (gap)

- `docs/operations/` ha 12 documenti, ma **nessuno è un runbook operativo generico per
  incidenti**: sono tutti guide a singole funzionalità/sync (es. `sports_scheduler.md`,
  `sports_data_quality.md`, `admin_operator_bootstrap.md`).
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

## Tooling proposto

Nessun nuovo tool: la card è principalmente documentale, con riuso di
osservabilità/audit/backup già pianificati/esistenti (`observability_baseline.md`,
EP11-03 audit log, restore EP12-05).

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

## Rischi e domande aperte

- Questa card dipende nei contenuti da EP12-04 (procedure di sicurezza) ed EP12-05
  (procedura di restore): se quelle non sono ancora implementate, i runbook corrispondenti
  possono essere scritti solo come bozza/placeholder in attesa.
- Il processo di supporto pilot (canale, SLA) richiede una decisione organizzativa del
  team, non solo tecnica.
