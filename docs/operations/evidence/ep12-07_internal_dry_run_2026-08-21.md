# EP12-07 — Evidenza dry-run interno del gate Beta

| Campo | Valore |
| --- | --- |
| Data esecuzione | 2026-08-21 |
| Tipo | tabletop deterministico, dati interamente sintetici |
| Ambiente | nessun servizio avviato, nessuna chiamata esterna |
| Registro | [`ep12-07_internal_dry_run_register_2026-08-21.csv`](./ep12-07_internal_dry_run_register_2026-08-21.csv) |
| Esito package validator | PASS |
| Esito decisionale simulato | primo caso NO-GO, dopo remediation GO simulato |

Questa evidenza prova che processo, schema e regole decisionali sono utilizzabili. Non
prova onboarding, utilizzo, consenso, KPI o approvazione di persone reali e **non chiude
EP12-07**.

## Preparazione del tabletop

- Ruoli fittizi: `decision_owner`, `pilot_coordinator`, `incident_coordinator`,
  `platform_owner`, `security_owner`, `privacy_contact`, `league_admin`.
- Coorte fittizia: `PILOT-L01`, `PILOT-L02`, `PILOT-L03`; nessun mapping a persone.
- Finestra fittizia congelata: 28 giorni e 4 turni per lega.
- Soglie congelate prima del calcolo: quelle marcate `PROPOSTA` nel
  [processo pilot](../beta_pilot_gate.md).
- Fonti `SIM-*`: riferimenti opachi esplicitamente sintetici; nessun ticket, log, account,
  token, email, IP o dato utente reale.

## Scenario 1 — prova del percorso NO-GO

Il facilitatore ha presentato il registro senza la riga `CAPACITY_RUN_PASS`, simulando
un summary k6 finale non disponibile. Il reviewer tecnico ha classificato il KPI come
non misurabile. Il decision owner simulato ha scelto **NO-GO**, senza trasformare
l'assenza in `N/A` e senza cambiare la soglia.

Remediation tabletop:

1. owner `platform_owner`;
2. azione: eseguire smoke k6 sulla build candidata e conservare summary redatto;
3. evidenza attesa: una riga `CAPACITY_RUN_PASS` con frazione dei run verdi;
4. retest: rieseguire il validatore sulla stessa finestra congelata;
5. rischio durante l'attesa: nessun invito e nessun accesso pilot.

## Scenario 2 — dataset completo

Sono state aggiunte le righe sintetiche full e smoke, con
`CAPACITY_RUN_PASS=2/2`. Il validatore ha controllato:

- 3 leghe con 8 partecipanti aggregati ciascuna, 28 giorni e 4 turni per lega;
- completamento flusso 43/45 (95,56%) complessivo e almeno 93,33% per lega; i 15
  checkpoint per lega sono i 3 passi di onboarding una volta più 3 passi operativi per
  ciascuno dei 4 turni;
- zero blocker, zero P0 e zero P1 aperti;
- supporto 9/10 complessivo e 1/1 per P0/P1;
- capacità 2/2 (full entro 30 giorni e smoke entro 7), zero eventi/finding security
  High/Critical;
- intervallo backup massimo 23,5 h e durata tecnica del restore isolato 24 min, sotto il
  budget EP12-05 di 30 min e senza chiamarla RTO;
- nessun restore reale, quindi i due KPI actual-recovery sono `not_applicable` con motivo;
- score qualitativo 13/3 (4,33/5) e recommendation intent 3/3;
- schema, alias, timestamp, source type, link locali e assenza dei pattern minimi PII/
  segreti.

Tutti i criteri sintetici rispettano le soglie, quindi l'algoritmo restituisce **GO
simulato**. In un pilot reale il risultato deve comunque essere riesaminato e firmato da
persone assegnate usando il template; lo script non ha autorità decisionale.

## Comando ed esito

```text
> python infra/scripts/verify_beta_pilot_gate.py
EP12-07 package: PASS
Links checked: PASS (34)
Template register: PASS (header only)
Dry-run register: PASS (31 rows, privacy-safe schema)
Synthetic missing-evidence scenario: NO-GO (tabletop only)
Synthetic gate evaluation: GO (tabletop only)
```

Controlli statici aggiuntivi eseguiti al termine:

```text
python -m py_compile infra/scripts/verify_beta_pilot_gate.py
git diff --check
```

Entrambi devono risultare PASS nel run finale della card.

## Limiti e blocchi umani osservati

Il tabletop ha confermato che prima di invitare leghe reali devono ancora essere
ratificati soglie/protocollo e assegnati ruoli, canali, archivio ticket, retention,
sorgente log aggregata, storage offsite/alert e cutover DR. Devono inoltre essere
completate la verifica Must M1–M4 richiamata dall'indice e l'approvazione privacy. Nessun
artefatto sintetico risolve questi blocchi.
