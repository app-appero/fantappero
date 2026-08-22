# Processo pilot e gate Beta

Pacchetto operativo EP12-07 per selezionare le leghe pilota, raccogliere misure
privacy-safe e registrare una decisione riproducibile. Il pacchetto e il dry-run interno
sono pronti; **il pilot reale non è stato eseguito e il gate Beta non è chiuso**.

Le quantità, le durate e le soglie indicate come `PROPOSTA` devono essere ratificate dal
team prima del primo invito. Una modifica dopo l'avvio richiede motivazione, approvatore
e data nel registro decisionale: non si possono adattare le soglie ai risultati già
osservati.

## 1. Autorità e decisioni bloccanti

| Ruolo | Responsabilità | Separazione minima | Stato iniziale |
| --- | --- | --- | --- |
| Decision owner | ratifica protocollo/soglie e firma GO o NO-GO | non può sostituire da solo il privacy contact su questioni privacy | da assegnare |
| Pilot coordinator | selezione, onboarding, calendario, registro e report | non autocertifica evidenze tecniche | da assegnare |
| Incident coordinator + backup | triage e comunicazioni secondo EP12-06 | almeno due nominativi | da assegnare |
| Platform owner + backup | deploy, osservabilità, backup e cutover DR | doppia approvazione per restore/switch | da assegnare |
| Security owner | classifica e chiude/accetta i finding | approva gli incidenti security | da assegnare |
| Privacy contact | approva informativa, consenso/acknowledgement e retention | decisione umana, non automatizzata | da assegnare |
| League admin pilot | conferma composizione lega e checkpoint di flusso | uno per lega | da selezionare |

Prima dell'onboarding il team deve inoltre scegliere e annotare, in un archivio ad
accesso ristretto e non nel repository:

- canale partecipanti, canale interno urgente e sistema ticket/evidenze;
- copertura e obiettivi di risposta, partendo dalle proposte EP12-06;
- sorgente aggregata dei log/health del deployment pilot e relativa retention;
- destinazione offsite dei backup, monitor/alert del job e comando di cutover DR;
- retention effettiva dei registri, partendo dalla proposta di 90 giorni dopo la
  decisione per ticket/survey e 30 giorni per la mappa alias-identità;
- nomi delle persone per tutti i ruoli sopra e sostituti richiesti.

L'assenza di uno solo di questi elementi produce **NO-GO all'avvio**. I valori non sono
inventati nel repo perché dipendono dall'organizzazione e dal deployment reali.

## 2. Protocollo proposto

### Dimensione e durata (`PROPOSTA`, da ratificare)

- 3–5 leghe, ciascuna con 6–12 partecipanti attivi e un league admin;
- almeno 28 giorni **e** almeno 4 turni fantacalcistici completi per ogni lega;
- una sola coorte iniziale; nuove leghe dopo l'avvio sono registrate come coorte distinta
  e non estendono retroattivamente il denominatore;
- ambiente pilot separato dai test e privo di premi/operazioni finanziarie dipendenti
  dall'esito della Beta.

La dimensione cerca varietà sufficiente senza superare la capacità di supporto manuale.
Il decision owner può ratificare valori diversi solo prima dell'invito e deve riportarli
nel template decisionale.

### Criteri di ammissione delle leghe

Una lega è ammessa solo se:

1. rientra nella dimensione ratificata e identifica un league admin disponibile ai
   checkpoint settimanali;
2. ogni partecipante soddisfa i requisiti di eleggibilità definiti nei termini/privacy
   approvati; finché un responsabile non decide diversamente, non coinvolgere minori;
3. accetta l'uso sperimentale, le funzioni incluse/escluse e il canale di supporto;
4. non dipende dalla Beta per denaro, obblighi legali o dati irrecuperabili;
5. accetta di segnalare solo identificativi pseudonimi/correlation ID e di non inserire
   password, token, email o dati personali nei report tecnici;
6. può completare il percorso registrazione → lega → rosa → formazione → risultato →
   mercato e almeno quattro turni nel periodo concordato.

Non selezionare soltanto utenti del team: il tabletop interno verifica il processo, non
sostituisce una coorte reale.

## 3. Gate di ingresso prima degli inviti

Il pilot coordinator allega o riferisce evidenze versionate e marca ogni riga
`PASS`, `FAIL` o `N/A` motivato. `N/A` non è ammesso sui gate obbligatori.

| Gate | Evidenza minima reale | Esito richiesto |
| --- | --- | --- |
| EP12-01 flusso critico | [card e comandi E2E](./beta_readiness/ep12-01_suite_e2e.md) | suite Playwright critica verde su build candidata |
| EP12-02 invarianti | [property/concurrency](./beta_readiness/ep12-02_test_proprieta_concorrenza.md) | suite mirate verdi sulla build candidata |
| EP12-03 capacità | [baseline](./evidence/ep12-03_capacity_2026-08-21.md) e [runbook](./performance_capacity.md) | almeno smoke verde; profilo steady/spike non più vecchio di 30 giorni o dopo cambi critici |
| EP12-04 sicurezza | [security review](./beta_readiness/ep12-04_security_review.md) | zero finding Critical/High aperti non accettati; rischi residui esplicitamente accettati |
| EP12-05 recuperabilità | [drill](./evidence/ep12-05_restore_drill_2026-08-21.md) e [runbook](./backup_disaster_recovery.md) | backup/restore drill verde; storage offsite, alert e cutover del deployment compilati |
| EP12-06 supporto | [simulazioni](./evidence/ep12-06_runbook_simulations_2026-08-21.md), [processo](./pilot_support_process.md) e [runbook](./pilot_incident_runbooks.md) | simulazioni verdi; ruoli, canali e obiettivi ratificati |
| M1–M4 | verifica puntuale richiamata nell'[indice M5](./beta_readiness/README.md) | nessun Must pertinente non verificato |
| Privacy/aspettative | testo approvato e acknowledgement conservati nel sistema ristretto scelto | 100% partecipanti prima dell'accesso |

Non copiare nel report le credenziali, i report raw di scanner o gli acknowledgement con
PII. È sufficiente un riferimento opaco all'evidenza protetta e il relativo owner.

## 4. Onboarding e aspettative

### Sequenza operativa

1. Il decision owner congela versione del protocollo, soglie, build candidata e finestra.
2. Il pilot coordinator assegna alias `PILOT-Lnn` alle leghe; il mapping con identità reali
   resta nel sistema ristretto, mai nel Git, nei log applicativi o nel CSV KPI.
3. Privacy contact e league admin presentano il testo approvato. L'acknowledgement viene
   registrato fuori repo prima di creare/abilitare l'accesso.
4. Il platform owner verifica readiness, backup recente, alert e accesso supporto.
5. Ogni league admin completa uno smoke guidato e conferma i sei step del flusso critico.
6. Il coordinator apre i checkpoint settimanali, registra KPI aggregati e collega solo
   riferimenti redatti.
7. A fine finestra congela il registro, calcola il gate e prepara il template di
   decisione. Ogni correzione successiva è append-only con motivo e approvatore.

### Contenuto minimo della comunicazione

Il testo finale deve essere approvato dal privacy contact e deve spiegare chiaramente:

- che si tratta di una Beta assistita, durata e funzioni effettivamente incluse;
- rischi noti e limitazioni: possibili interruzioni/correzioni, assenza di undo per
  transazioni mercato terminali e limiti indicati nei runbook;
- dati necessari al servizio e feedback raccolto, finalità, retention, accessi e contatto
  per esercitare i diritti applicabili; il repository non sostituisce un'informativa;
- canale/orari/obiettivi di risposta, modalità P0 e assenza di una garanzia pubblica di
  risoluzione entro tali obiettivi;
- come ritirarsi dal pilot senza penalità e come verranno gestiti/cancellati i dati;
- divieto di inviare token, password, dump o PII nei ticket e nei questionari tecnici.

Checklist per partecipante, conservata fuori repo: versione testo, timestamp UTC,
acknowledgement sì/no, versione build/protocollo, alias lega e riferimento opaco. Non
registrare qui nome, email, IP o user ID.

## 5. Registro manuale privacy-safe

Usare [il CSV vuoto versionato](./templates/ep12-07_pilot_register.csv) come schema, ma
conservare il registro reale nel sistema ristretto scelto. Nel repo vanno soltanto
aggregati redatti necessari alla decisione.

Regole:

- `league_alias`: solo `PILOT-Lnn` oppure `ALL`; il mapping è separato;
- `period_id`: periodo predefinito (`W01`, `W02`, `FINAL`, ecc.);
- `owner_role`: solo ruolo, mai nome o account della persona;
- `source_type`: uno tra `e2e`, `k6`, `ticket`, `checkpoint`, `security_review`,
  `backup_log`, `dr_drill`, `survey`;
- `source_ref` ed `evidence_ref`: ID opachi o path a evidenza redatta, mai URL con token;
- `value`: valore normalizzato; `numerator`/`denominator` rendono verificabili percentuali
  e medie quando applicabili;
- `notes_redacted`: categoria controllata o nota breve già redatta. Non trascrivere
  feedback libero: classificarlo e tenere l'originale nel sistema ristretto;
- `status`: `collected`, `validated`, `not_applicable` motivato oppure `corrected`; al
  gate contano solo righe validate e le sole N/A esplicitamente ammesse;
- nessuna cella libera può iniziare con `=`, `+`, `-` o `@`, per evitare formule quando
  il CSV viene aperto in un foglio di calcolo;
- righe append-only; una rettifica aggiunge una riga con stato `corrected` e riferimento
  alla precedente, senza riscrivere la cronologia.

La retention proposta è: cancellare la mappa alias-identità entro 30 giorni dalla
chiusura e ticket/survey grezzi entro 90 giorni dalla decisione. La copia redatta della
decisione segue la retention documentale del progetto. Il privacy contact deve
ratificare o sostituire questi valori in base a informativa, base giuridica e obblighi
applicabili prima della raccolta; una richiesta di ritiro segue quella decisione, non una
cancellazione improvvisata dal registro Git.

## 6. KPI, formule, sorgenti e soglie

Tutte le soglie seguenti sono `PROPOSTA`. Vanno ratificate e congelate prima del pilot.

| KPI ID | Definizione e formula | Sorgente reale | Soglia proposta |
| --- | --- | --- | --- |
| `ACTIVE_LEAGUES` | leghe ammesse con almeno un turno completato nel periodo | checkpoint league admin | 3–5 leghe |
| `ACTIVE_PARTICIPANTS` | partecipanti che completano almeno un checkpoint pianificato, solo conteggio aggregato per alias lega | checkpoint league admin | 6–12 per lega; totale uguale alla somma delle leghe |
| `PILOT_DURATION_DAYS` | giorni UTC tra apertura e chiusura della finestra congelata, per lega | calendario protocollo + checkpoint | almeno 28 giorni per lega |
| `COMPLETED_ROUNDS` | turni completi per lega nel periodo | checkpoint league admin, verificato su UI/API | almeno 4 per ogni lega e almeno 28 giorni |
| `CRITICAL_FLOW_COMPLETION` | checkpoint completati / checkpoint pianificati e congelati: registrazione, lega e rosa una volta in onboarding; formazione, risultato e mercato una volta per turno | checklist settimanale league admin; non analytics | almeno 90% complessivo e almeno 80% per ogni lega |
| `CRITICAL_FLOW_BLOCKERS_OPEN` | difetti aperti che impediscono uno dei sei step e non hanno workaround approvato | archivio ticket scelto | 0 al gate |
| `SUPPORT_ACK_WITHIN_TARGET` | ticket presi in carico entro l'obiettivo EP12-06 / ticket con obiettivo applicabile | timestamp del sistema ticket scelto | 100% P0/P1 e almeno 90% complessivo; con denominatore zero, `N/A-no-ticket` è valido solo se l'estrazione dimostra zero ticket |
| `P0_INCIDENTS` | incidenti P0 confermati nel periodo | ticket incidenti EP12-06 | 0 |
| `P1_OPEN_AT_GATE` | incidenti P1 non risolti/accettati al gate | ticket incidenti EP12-06 | 0 |
| `CAPACITY_RUN_PASS` | run k6 controllati che rispettano tutte le threshold / run richiesti | summary redatto k6 EP12-03 | 100%: full steady/spike entro 30 giorni (e dopo cambi critici) **e** smoke finale entro 7 giorni |
| `SECURITY_HIGH_CRITICAL` | incidenti confermati o finding nuovi High/Critical non accettati | security review + ticket security | 0 |
| `BACKUP_MAX_INTERVAL_HOURS` | massimo intervallo UTC fra inizio pilot, backup validi consecutivi e chiusura della finestra | log/manifest job backup del deployment | massimo 24 h |
| `DR_DRILL_RESTORE_MINUTES` | durata tecnica del restore isolato verificato; non è un RTO end-to-end | report drill EP12-05 | massimo 30 min, run entro 30 giorni |
| `ACTUAL_RECOVERY_RPO_HOURS` | perdita temporale effettiva se è avvenuto un restore reale | ticket DR + manifest | massimo 24 h; `N/A` se nessun restore |
| `ACTUAL_RECOVERY_RTO_MINUTES` | dichiarazione incidente → servizio verificato, se restore reale | timeline ticket DR | massimo 120 min; `N/A` se nessun restore |
| `QUALITATIVE_SCORE` | media dei punteggi 1–5 alla domanda congelata “Il flusso di lega è utilizzabile senza assistenza continua?” | survey aggregata per lega | media almeno 4,0 e risposta da tutte le leghe |
| `RECOMMENDATION_INTENT` | league admin che continuerebbero dopo la Beta / league admin rispondenti | survey sì/no aggregata | almeno 80%, risposta da tutte le leghe |

`/metrics` è process-local con più worker e non rappresenta un contatore aggregato del
pilot. Può aiutare la diagnosi ma non è fonte autorevole per disponibilità o tasso 5xx.
Analogamente k6 prova la capacità controllata, non l'esperienza reale. Se il deployment
aggiunge una sorgente aggregata valida, il team può aggiungere un KPI prima del freeze;
la mancanza di tale integrazione non deve essere nascosta con dati inventati.

Feedback qualitativo: usare punteggi e categorie predefinite (`onboarding`, `league`,
`roster`, `lineup`, `results`, `market`, `support`, `other-redacted`). Citazioni testuali
si pubblicano solo previa revisione privacy; non sono necessarie al gate.

## 7. Decisione GO / NO-GO

Usare [il template versionato](./templates/ep12-07_gate_decision.md). Il decision owner
può firmare soltanto uno dei due esiti:

- **GO**: gate di ingresso soddisfatti, dimensione/durata raggiunte, tutti i KPI
  obbligatori misurati da fonti verificabili e ogni soglia ratificata rispettata;
- **NO-GO**: una precondizione manca, un KPI obbligatorio non è misurabile/non rispetta
  soglia, oppure esiste un rischio non accettato. “Dato mancante” non equivale a PASS.

Non esiste un `conditional GO`: una deroga è una nuova soglia approvata prima del pilot
oppure un rischio formalmente accettato con owner/scadenza prima della firma. Se la
modifica avviene dopo aver visto i risultati, l'esito corrente resta NO-GO e si pianifica
un nuovo tentativo.

### Remediation del NO-GO

Per ogni gate fallito registrare causa, owner, azione verificabile, scadenza, evidenza
attesa, rischio durante l'attesa e campo di retest. Il nuovo tentativo deve dichiarare se
riusa dati precedenti o apre una nuova finestra; incidenti, criteri e soglie originarie
restano conservati. Il decision owner firma nuovamente solo dopo evidenze del retest.

## 8. Dry-run interno ripetibile

Il tabletop usa solo alias e dati sintetici in
[registro di prova](./evidence/ep12-07_internal_dry_run_register_2026-08-21.csv). Il
[report versionato](./evidence/ep12-07_internal_dry_run_2026-08-21.md) dimostra percorso,
escalation NO-GO e ricalcolo del caso corretto; non è evidenza di utenti reali.

Validare pacchetto, link relativi, schema CSV, privacy minima e calcolo del caso sintetico:

```bash
python infra/scripts/verify_beta_pilot_gate.py
```

Il validatore non contatta servizi esterni e non legge il registro reale. Un PASS prova
soltanto completezza/coerenza degli artefatti versionati.
