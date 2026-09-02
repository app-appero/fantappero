# M5 — Beta readiness (EP12): indice di pianificazione

Questa cartella raccoglie la pianificazione dettagliata delle 7 card dell'Epic EP12
("Come team vogliamo rilasciare una Beta osservabile, sicura e recuperabile"), ultima
milestone (M5) prevista dal pacchetto `docs/doc_fantapperò/FantAppero_Pacchetto_Completo_M0.5-M5_v0.3/`.

**Stato aggiornato al 2026-08-21 sul branch `claude/M5`**: EP12-01…06 sono implementate,
validate e accompagnate dalle rispettive evidenze. Per EP12-07 il pacchetto operativo e
il dry-run interno sono predisposti; il pilot reale (onboarding e osservazione delle
leghe), la misura dei KPI e la decisione go/no-go richiedono ancora il team nel tempo.

## Stato corrente

| Card | Stato | Evidenza principale |
| --- | --- | --- |
| EP12-01 | completata | suite Playwright critica e seed E2E |
| EP12-02 | completata | property test ledger e concorrenza formazione |
| EP12-03 | completata | [`ep12-03_capacity_2026-08-21.md`](../evidence/ep12-03_capacity_2026-08-21.md) |
| EP12-04 | completata | finding e prove nella [security review](./ep12-04_security_review.md) |
| EP12-05 | completata | [`ep12-05_restore_drill_2026-08-21.md`](../evidence/ep12-05_restore_drill_2026-08-21.md) |
| EP12-06 | completata | [`ep12-06_runbook_simulations_2026-08-21.md`](../evidence/ep12-06_runbook_simulations_2026-08-21.md) |
| EP12-07 | pacchetto predisposto; pilot pendente | [processo e gate](../beta_pilot_gate.md), [dry-run](../evidence/ep12-07_internal_dry_run_2026-08-21.md); criteri reali/decisione non ancora misurati |

## Precondizione: Epic Must (M1–M4)

Tutte le card EP12 dichiarano come dipendenza "Tutte le Epic Must pertinenti". Dalla
ricognizione del repo:

- **M3 (EP07 punteggi/classifica, EP08 mercato) e M4 (EP09 notifiche, EP10 assistente AI,
  EP11 entitlement/audit)** hanno commit granulari `feat: EPxx-yy...` e moduli backend
  corrispondenti (`fantasy_ratings`, `fantasy_turns`, `market`, `notifications`,
  `ai_assistant`, `billing`, `admin`). Considerate coperte.
- **M1 (EP02 account, EP03 leghe, EP04 dati sportivi) e M2 (EP05 rose, EP06 formazioni)**
  non hanno commit granulari per singola card (commit generici `M1`, `M2 + M3-1`), ma i
  moduli backend esistono (`auth`, `authorization`, `leagues`, `sports_data`,
  `fantasy_teams`, `fantasy_lineups`). **Prima di dichiarare M5 sbloccata formalmente**,
  verificare puntualmente (test esistenti + endpoint attivi) in particolare:
  - EP04-07 — Pannello qualità dati (esiste doc `docs/operations/sports_data_quality.md`,
    verificare che l'UI/endpoint corrispondenti siano effettivamente implementati)
  - EP06-05/06/07 — Tre mosse tattiche, formazione precedente/bozze, rinvii e variazioni
    orario (verificare in `backend/src/fantasy_lineups/`)

Questo controllo puntuale non è stato eseguito in questa sessione (è fuori scope della
pianificazione EP12) ed è segnalato come rischio comune a tutte le card in ciascun piano.

## Le 7 card

| Card | Titolo | Documento | Dipende da |
|---|---|---|---|
| EP12-01 | Suite end-to-end critica | [ep12-01_suite_e2e.md](./ep12-01_suite_e2e.md) | M1–M4 |
| EP12-02 | Test proprietà e concorrenza | [ep12-02_test_proprieta_concorrenza.md](./ep12-02_test_proprieta_concorrenza.md) | M1–M4 |
| EP12-03 | Performance e capacità | [ep12-03_performance_capacita.md](./ep12-03_performance_capacita.md) | EP12-01 (dataset/scenario), EP12-02 (no regressioni sotto stress) |
| EP12-04 | Security review | [ep12-04_security_review.md](./ep12-04_security_review.md) | M1–M4 (superficie da rivedere) |
| EP12-05 | Backup e disaster recovery | [ep12-05_backup_disaster_recovery.md](./ep12-05_backup_disaster_recovery.md) | Nessuna (indipendente, infra) |
| EP12-06 | Runbook e supporto pilot | [ep12-06_runbook_supporto_pilot.md](./ep12-06_runbook_supporto_pilot.md) | EP12-04, EP12-05 (contenuti da citare nei runbook) |
| EP12-07 | Pilot e gate Beta chiusa | [ep12-07_pilot_gate_beta.md](./ep12-07_pilot_gate_beta.md) | EP12-01…06 (tutte, è il gate finale) |

## Sequenziamento consigliato

1. **EP12-02** (test proprietà/concorrenza) — usa solo infrastruttura pytest già esistente,
   nessun tool nuovo obbligatorio (Hypothesis è opzionale). Rischio più basso, valore alto:
   verifica invarianti critici (crediti, assegnazioni) prima di costruire altro sopra.
2. **EP12-01** (suite E2E) — richiede scegliere e introdurre un framework E2E (proposta:
   Playwright). Propedeutica a EP12-03 perché fornisce lo scenario/dataset "flusso
   completo" riusabile anche per i test di carico.
3. **EP12-04** (security review) — in parte indipendente, può procedere in parallelo a
   EP12-01/02; usa soprattutto tooling di analisi (pip-audit, bandit, npm audit) e review
   manuale, non richiede modifiche architetturali salvo remediation puntuali.
4. **EP12-05** (backup/DR) — indipendente dal resto, tocca solo `compose.yaml`/infra e
   script/documentazione. Può essere fatta in qualunque momento.
5. **EP12-03** (performance/capacità) — dopo EP12-01 (riusa lo scenario E2E come base di
   carico) ed EP12-02 (in modo che i test di carico non stressino codice con bug di
   concorrenza già noti).
6. **EP12-06** (runbook) — completata tecnicamente dopo EP12-04/05; ruoli, canali e
   cutover deployment-specifico devono essere confermati prima del pilot.
7. **EP12-07** (pilot e gate Beta) — pacchetto tecnico/procedurale e tabletop completati.
   **Non interamente implementabile da un agente**: richiede onboarding di leghe/utenti
   reali nel tempo. Criteri misurati e decisione firmata restano pendenti.

## Criteri di gate complessivo "Beta chiusa" (da EP12-07)

La Beta si considera pronta per il gate finale quando, per ciascuna delle card
EP12-01…06, sono soddisfatti i rispettivi criteri di accettazione **con evidenze
collegate** (report di run, log, dashboard, documenti firmati/approvati) e quando i
criteri di uscita specifici del pilot (vedi `ep12-07_pilot_gate_beta.md`) sono misurati e
la decisione go/no-go è registrata.
