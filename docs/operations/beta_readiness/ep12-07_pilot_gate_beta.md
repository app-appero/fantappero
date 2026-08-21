# EP12-07 — Pilot e gate Beta chiusa

## Stato implementazione (branch `claude/M5`)

**Pacchetto operativo predisposto e dry-run interno completato il 2026-08-21; pilot
reale, KPI osservati e decisione finale ancora umani e pendenti.**

- [Processo pilot e gate Beta](../beta_pilot_gate.md): criteri di ammissione, proposta
  3–5 leghe con 6–12 partecipanti per lega, durata minima 28 giorni e 4 turni, onboarding,
  aspettative/privacy, ruoli, KPI con sorgenti reali e soglie da ratificare.
- [Registro manuale privacy-safe](../templates/ep12-07_pilot_register.csv) e
  [template GO/NO-GO con remediation](../templates/ep12-07_gate_decision.md).
- Checklist tracciabile EP12-01…06 e Must M1–M4; EP12-03 è distinto fra capacità
  controllata e comportamento reale, EP12-05 fra restore tecnico isolato e RTO
  end-to-end, EP12-06 fra proposte operative e ruoli/canali approvati.
- `infra/scripts/verify_beta_pilot_gate.py` valida senza dipendenze schema, link,
  placeholder obbligatori, alias/timestamp/sorgenti e calcola il solo caso sintetico.
- [Evidenza del tabletop](../evidence/ep12-07_internal_dry_run_2026-08-21.md): un caso
  senza misura produce NO-GO; dopo remediation il dataset interamente sintetico produce
  GO simulato.

La card **non soddisfa ancora** il criterio “criteri di uscita misurati e decisione
registrata”: prima degli inviti il team deve assegnare persone/canali, ratificare
protocollo e soglie, completare i gate deployment/privacy; poi deve eseguire il pilot
reale nel tempo e firmare GO o NO-GO. Il tabletop non sostituisce questi passi.

| Metadato | Valore |
| --- | --- |
| Card | EP12-07 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | EP12-01…06 (tutte: è il gate finale della milestone M5) |
| Stima originale | 3–5 giorni |

## Obiettivo e scope

Onboardare leghe pilota, raccogliere KPI e decidere il go/no-go; criteri di uscita
misurati e decisione registrata, con piano, dati di test, responsabile ed evidenze.

## Nota importante: natura della card

A differenza delle altre 6 card EP12, questa **non è implementabile interamente da un
agente**: richiede l'onboarding di leghe/utenti reali che usano il prodotto nel tempo
(un campionato ha una durata di settimane/mesi), la raccolta di feedback umano e una
decisione di business/prodotto. Il contributo possibile in una sessione di lavoro
tecnico è limitato a: **predisporre il processo, gli strumenti di misura e i template di
decisione**, non a eseguire il pilot.

## Ricognizione iniziale (gap tecnici ora coperti)

- Il processo di onboarding, i KPI Beta e il template decisionale mancavano: sono ora
  disponibili negli artefatti collegati nello stato implementazione.
- EP12-01…06 dispongono ora di implementazione/evidenze collegate. Restano da ratificare
  per l'ambiente reale i valori proposti e i blocchi organizzativi/deployment esplicitati
  da EP12-06 e dal processo pilot.
- Onboarding reale, osservazione nel tempo, feedback umano e decisione di business non
  sono simulabili né dichiarati conclusi dal repository.

## Piano d'azione

1. **Coperto — criteri di ammissione**: dimensione, durata e requisiti tecnici sono nel
   processo pilot; valori e responsabili restano da ratificare prima degli inviti.
2. **Coperto — KPI Beta** (categorie, formule, fonti e soglie proposte):
   - Affidabilità: tasso di errore percepito, incidenti aperti (da runbook EP12-06),
     rispetto SLO (da EP12-03).
   - Adozione/usabilità: completamento del flusso critico (stesso flusso testato in
     EP12-01) da parte di utenti reali, tasso di abbandono per step.
   - Sicurezza: nessun incidente critico/alto emerso durante il pilot (collegato a
     EP12-04).
   - Recuperabilità: eventuali interventi di backup/restore richiesti durante il pilot e
     relativo tempo di risoluzione (collegato a EP12-05).
3. **Coperto — raccolta KPI**: scelto un registro CSV manuale con fonti reali e survey
   aggregata. Non è stata inventata un'integrazione analytics; le metriche in-process
   restano soltanto diagnostiche e non sono usate come aggregato autorevole.
4. **Coperto proceduralmente — selezione e comunicazione**: sequenza, contenuto minimo e
   riuso del supporto EP12-06 sono documentati; persone, canali e testo privacy sono
   ancora scelte umane bloccanti.
5. **Coperto — template decisionale**: GO/NO-GO, evidenze, autorità, remediation e retest
   sono predisposti e verificati con dati sintetici.
6. **Pendente umano — eseguire il pilot e registrare la decisione finale**: richiede
   tempo reale, utenti reali e firma del decision owner.

## Tooling implementato

Nessuna nuova dipendenza o analytics esterna. Il registro è manuale e il validatore usa
solo la standard library Python; le fonti di ogni KPI sono esplicite nel processo.

## Dati di test

Il dato di accettazione resta quello delle leghe reali. Per verificare la preparazione è
stato creato un registro interamente sintetico con tre alias e due percorsi decisionali:
evidenza mancante → NO-GO; dataset completo → GO simulato. Non è contato come pilot.

## Criteri di accettazione (dalla card, ancora pendenti sul pilot reale)

- Criteri di uscita misurati e decisione registrata.
- Evidenze collegate alla card.

## Test minimi richiesti

Non applicabili nel senso tecnico standard (unit/integration/E2E): la verifica della
preparazione è procedurale. Processo, template e registro sono stati validati con il
tabletop versionato e con `python infra/scripts/verify_beta_pilot_gate.py`. L'esecuzione
del pilot e la firma del gate restano verifiche umane successive.

## Rischi e domande aperte

- EP12-01…06 sono implementate e collegate, ma l'ammissione reale richiede un run recente
  sulla build candidata e la risoluzione delle decisioni organizzative/deployment.
- La durata di un pilot reale (settimane/mesi, legata al calendario di un campionato) non
  è comprimibile in una sessione di lavoro tecnico: va pianificata come attività
  calendarizzata dal team, non come task eseguibile in una singola sessione.
- I valori soglia e il protocollo sono proposti nel pacchetto per rendere il dry-run
  verificabile, ma autorità e team devono ratificarli e congelarli prima del primo invito.
