# Decisione gate Beta — EP12-07

> Copiare questo template nel sistema decisionale ristretto. Pubblicare nel repository
> soltanto una versione redatta senza nomi, contatti, token, ID utente o dati personali.

## Controllo documento

- Decision ID: `REQUIRED`
- Versione protocollo/build: `REQUIRED`
- Finestra pilot UTC: `REQUIRED`
- Data decisione UTC: `REQUIRED`
- Decision owner (riferimento organizzativo, non PII nella copia pubblica): `REQUIRED`
- Revisori security/privacy/platform/support: `REQUIRED`
- Soglie ratificate prima dell'invito, riferimento e data: `REQUIRED`

## Coorte e copertura

- Leghe ammesse/completate: `REQUIRED`
- Partecipanti aggregati (nessun identificativo): `REQUIRED`
- Durata giorni e turni completi per lega: `REQUIRED`
- Build/deployment osservato: `REQUIRED`
- Variazioni dal protocollo congelato: `NONE` oppure `REQUIRED`

## Gate EP12-01…06 e M1–M4

| Gate | PASS/FAIL | Evidenza redatta | Revisore/UTC |
| --- | --- | --- | --- |
| EP12-01 E2E | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| EP12-02 proprietà/concorrenza | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| EP12-03 capacità | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| EP12-04 sicurezza | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| EP12-05 backup/DR | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| EP12-06 runbook/supporto | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| Must M1–M4 pertinenti | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| Aspettative/privacy acknowledgement | `REQUIRED` | riferimento protetto aggregato `REQUIRED` | `REQUIRED` |

## KPI congelati e risultati

| KPI ID | Soglia ratificata | Valore/frazione | PASS/FAIL/N/A motivato | Fonte/evidenza redatta |
| --- | --- | --- | --- | --- |
| `ACTIVE_LEAGUES` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `ACTIVE_PARTICIPANTS` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `PILOT_DURATION_DAYS` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `COMPLETED_ROUNDS` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `CRITICAL_FLOW_COMPLETION` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `CRITICAL_FLOW_BLOCKERS_OPEN` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `SUPPORT_ACK_WITHIN_TARGET` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `P0_INCIDENTS` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `P1_OPEN_AT_GATE` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `CAPACITY_RUN_PASS` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `SECURITY_HIGH_CRITICAL` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `BACKUP_MAX_INTERVAL_HOURS` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `DR_DRILL_RESTORE_MINUTES` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `ACTUAL_RECOVERY_RPO_HOURS` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `ACTUAL_RECOVERY_RTO_MINUTES` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `QUALITATIVE_SCORE` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |
| `RECOMMENDATION_INTENT` | `REQUIRED` | `REQUIRED` | `REQUIRED` | `REQUIRED` |

## Rischi, incidenti e qualità dei dati

- P0/P1 e incidenti security/DR, riferimenti redatti: `REQUIRED`
- Dati mancanti, esclusioni e motivazione: `REQUIRED`
- Rischi accettati con owner/scadenza: `REQUIRED`
- Conferma che `/metrics` process-local non sia stato usato come aggregato: `REQUIRED`
- Conferma assenza di PII/segreti negli allegati pubblicabili: `REQUIRED`

## Esito (selezionare esattamente uno)

- [ ] **GO** — tutti i gate obbligatori sono misurati e rispettati.
- [ ] **NO-GO** — almeno un gate manca o fallisce; compilare remediation.

Motivazione verificabile: `REQUIRED`

Firma/approvazione del decision owner e timestamp nel sistema ristretto: `REQUIRED`

## Remediation NO-GO e retest

| Gate/KPI | Causa | Azione verificabile | Owner role | Scadenza UTC | Evidenza attesa | Retest/finestra |
| --- | --- | --- | --- | --- | --- | --- |
| `REQUIRED_IF_NO_GO` | `REQUIRED_IF_NO_GO` | `REQUIRED_IF_NO_GO` | `REQUIRED_IF_NO_GO` | `REQUIRED_IF_NO_GO` | `REQUIRED_IF_NO_GO` | `REQUIRED_IF_NO_GO` |

Decision ID successiva oppure motivazione di chiusura: `REQUIRED_IF_NO_GO`
