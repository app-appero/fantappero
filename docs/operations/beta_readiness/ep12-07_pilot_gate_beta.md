# EP12-07 — Pilot e gate Beta chiusa

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

## Stato attuale nel repo (gap)

- Nessun processo di onboarding pilota documentato.
- Nessuna definizione di KPI Beta in nessun documento esistente.
- Nessun template/documento di decisione go/no-go.
- Le altre 6 card EP12 (di cui questa è il gate) non sono ancora implementate: questa
  card **non può essere completata** finché EP12-01…06 non producono le rispettive
  evidenze.

## Piano d'azione

1. **Definire i criteri di ammissione al pilot**: quante leghe, quanti utenti per lega,
   durata minima di osservazione, requisiti tecnici minimi già soddisfatti (tipicamente:
   EP12-01…06 con evidenze verdi) prima di invitare utenti reali.
2. **Definire i KPI Beta da raccogliere durante il pilot** (proposta di categorie, valori
   soglia da confermare col team):
   - Affidabilità: tasso di errore percepito, incidenti aperti (da runbook EP12-06),
     rispetto SLO (da EP12-03).
   - Adozione/usabilità: completamento del flusso critico (stesso flusso testato in
     EP12-01) da parte di utenti reali, tasso di abbandono per step.
   - Sicurezza: nessun incidente critico/alto emerso durante il pilot (collegato a
     EP12-04).
   - Recuperabilità: eventuali interventi di backup/restore richiesti durante il pilot e
     relativo tempo di risoluzione (collegato a EP12-05).
3. **Predisporre uno strumento di raccolta KPI**: valutare se riusare le metriche
   in-process già esistenti (`backend/src/observability/metrics.py`) più un log
   strutturato di eventi di prodotto (nuova istrumentazione minima, da definire in fase
   di implementazione), oppure una raccolta manuale/survey per la parte qualitativa
   (feedback utenti) — decisione da prendere in fase di implementazione, non qui.
4. **Definire il processo di selezione e comunicazione con le leghe pilota** (chi le
   invita, materiale di onboarding, canale di supporto — riusa il processo di supporto
   definito in EP12-06).
5. **Creare il template di decisione go/no-go**: criteri di uscita misurabili (soglie sui
   KPI del punto 2), formato del report finale, chi ha autorità di decisione, cosa succede
   in caso di no-go (remediation e nuovo tentativo, o rollback).
6. **Eseguire il pilot** (fuori scope di un'agente: richiede tempo reale e utenti reali) e
   **registrare la decisione finale** usando il template del punto 5.

## Tooling proposto

Nessun nuovo tool obbligatorio lato codice; eventuale instrumentazione minima di eventi
prodotto (punto 3) da valutare in fase di implementazione, riusando
`backend/src/observability/` invece di introdurre un sistema di analytics esterno per la
Beta.

## Dati di test

Non applicabile in senso stretto: il "dato" di questa card sono le leghe pilota reali. In
fase di preparazione, può essere utile validare il processo di onboarding con un "pilot
a tavolino" interno (team stesso come lega di prova) prima di invitare utenti esterni.

## Criteri di accettazione (dalla card)

- Criteri di uscita misurati e decisione registrata.
- Evidenze collegate alla card.

## Test minimi richiesti

Non applicabili nel senso tecnico standard (unit/integration/E2E): la "verifica" di
questa card è procedurale — il processo di onboarding e il template di decisione vanno
validati con un dry-run interno prima del pilot reale.

## Rischi e domande aperte

- **Questa card non può iniziare realisticamente finché EP12-01…06 non sono completate**,
  perché i KPI e i criteri di uscita dipendono direttamente dalle loro evidenze (SLO da
  EP12-03, assenza di vulnerabilità da EP12-04, RPO/RTO da EP12-05, runbook da EP12-06).
- La durata di un pilot reale (settimane/mesi, legata al calendario di un campionato) non
  è comprimibile in una sessione di lavoro tecnico: va pianificata come attività
  calendarizzata dal team, non come task eseguibile in una singola sessione.
- I valori soglia dei KPI e l'autorità di decisione go/no-go sono scelte di prodotto/
  business, non deducibili dal codice: questo documento propone la struttura del
  processo, non i valori.
