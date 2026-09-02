# Processo di supporto Beta pilot

Processo EP12-06 per ricezione, triage, comunicazione e chiusura dei problemi delle leghe
pilota. Ruoli e valori temporali sotto sono **proposte operative da confermare**: non sono
un impegno pubblico finché il team non compila la checklist finale.

## Decisioni obbligatorie prima dell'onboarding

| Decisione | Proposta Beta | Stato |
| --- | --- | --- |
| Canale partecipanti | un indirizzo email o form condiviso, non DM personali | da confermare |
| Canale urgenze interne | un unico canale del team con reperibile nominato | da confermare |
| Copertura | giorni feriali 09:00–18:00 Europe/Rome; P0 fuori fascia via escalation | da confermare |
| Coordinatore incidente primario/backup | due persone nominate | da assegnare |
| Platform owner primario/backup | due persone con accesso a deploy, secret e backup | da assegnare |
| Archivio ticket/evidenze | sistema con accesso ristretto e retention definita | da scegliere |
| Comando cutover DR | scheda specifica del deployment pilot | mancante/bloccante per il go-live |

EP12-07 non deve avviare leghe reali finché queste righe non sono risolte. Nessun canale
specifico viene inventato nel repository perché non esiste una integrazione supporto.

## Severità e obiettivi interni proposti

| Priorità | Criterio | Presa in carico | Primo aggiornamento | Aggiornamenti |
| --- | --- | --- | --- | --- |
| P0 | esposizione dati/segreti attiva, perdita dati ampia, servizio indisponibile per tutte le leghe | 15 min | 30 min | ogni 30 min |
| P1 | scoring/mercato errato con impatto su una lega o funzione critica bloccata | 1 h | 2 h | ogni 2 h |
| P2 | degrado con workaround, dati sportivi in ritardo senza risultato errato definitivo | 4 h lavorative | entro il giorno lavorativo | giornaliero |
| P3 | domanda, difetto cosmetico, richiesta non bloccante | 1 giorno lavorativo | 2 giorni lavorativi | a cambio stato |

Sono obiettivi di risposta, non tempi garantiti di risoluzione. RPO/RTO di EP12-05 restano
separati: 24 h/2 h sono obiettivi Beta definiti, non una misura end-to-end già provata.
Il drill locale ha misurato il solo percorso tecnico su un dataset ridotto; replica
offsite, selezione, approvazione e cutover reale devono ancora essere esercitati.

## Flusso del ticket

1. **Ricezione:** il supporto assegna ID, timestamp UTC, lega/utente interessato e
   conferma ricezione. Non chiedere password, token, dump o chiavi.
2. **Triage:** classificare P0–P3, tipo (`sports-data`, `scoring`, `security`, `data-loss`,
   `market`, `other`) e verificare se l'incidente è duplicato.
3. **Assegnazione:** P0/P1 hanno coordinatore ed esecutore distinti; le azioni ad ampio
   impatto richiedono una seconda approvazione.
4. **Diagnosi:** registrare ambiente, versione/commit, timeline UTC, correlation ID,
   endpoint/status e impatto. Collegare uno dei
   [runbook incidenti](./pilot_incident_runbooks.md).
5. **Comunicazione:** tradurre lo stato tecnico in impatto utente, workaround e prossima
   ora di aggiornamento; evitare ipotesi non verificate.
6. **Risoluzione:** eseguire la checklist di verifica del runbook e chiedere conferma al
   segnalante/amministratore lega quando applicabile.
7. **Chiusura:** annotare causa, cambiamenti, evidenze redatte, rischio residuo e follow-up.
   P0/P1 richiedono retrospettiva entro due giorni lavorativi (proposta).

Stati proposti: `new -> triaged -> investigating -> mitigating -> monitoring -> resolved`
oppure `blocked` con owner e data del prossimo controllo. La chiusura automatica non è
prevista.

## Template minimo di segnalazione

```text
Titolo:
Lega/ambiente:
Quando è iniziato (data e ora con fuso):
Cosa stavi facendo:
Risultato atteso:
Risultato osservato:
Impatto e utenti coinvolti:
URL/pagina e correlation ID, se visibile:
Screenshot senza dati personali o token (facoltativo):
```

Il supporto aggiunge:

```text
Ticket ID / priorità / tipo:
Coordinatore / esecutore / approvatore:
Timeline UTC:
Runbook e passo corrente:
Evidenze redatte:
Decisione, verifica, rischio residuo:
Prossimo aggiornamento:
```

## Escalation

- P0 sicurezza/dati: coordinatore + platform owner immediati; preservare evidenza prima
  del riavvio quando ciò non prolunga l'esposizione.
- Restore: seconda approvazione obbligatoria per backup e switch; seguire RB-04.
- Scoring/mercato: amministratore lega decide l'esito di dominio; l'operatore non cambia
  regole o dati fuori dagli endpoint supportati.
- Provider sportivo: escalare dopo un retry auditato fallito o indisponibilità/rate limit
  confermati; evitare loop di retry.
- Questione privacy/legale: coinvolgere un responsabile umano. Il software non determina
  obblighi di notifica.

## Metriche del supporto per EP12-07

Raccogliere per settimana, senza PII:

- numero ticket per priorità/tipo e lega pilota pseudonimizzata;
- tempo a presa in carico e primo aggiornamento;
- tempo a mitigazione/risoluzione e percentuale entro obiettivo proposto;
- incidenti riaperti, restore eseguiti, correzioni turno e problemi mercato senza undo;
- top cause e follow-up scaduti.

I KPI diventano gate soltanto dopo approvazione esplicita in EP12-07. Il repo non include
un sistema ticketing o un exporter di queste metriche; durante il pilot vanno raccolte
nel sistema scelto dal team.
