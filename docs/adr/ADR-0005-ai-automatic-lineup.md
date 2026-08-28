# ADR-0005 — Formazione automatica dei fantallenatori IA

| Metadato | Valore |
| --- | --- |
| Stato | Accettato (EP13-P05) — decisioni aperte risolte in fondo |
| Data | 2026-08-23 |
| Card | EP13-P05 |
| Dipendenza | ADR-0001 (confine provider); EP07-04 (formazione effettiva); EP13-P03 (mapping giornate) |
| Relazioni | [`../api/fantasy_lineups.md`](../api/fantasy_lineups.md); [`../api/fantasy_teams.md`](../api/fantasy_teams.md); [`../operations/sports_fixtures_sync.md`](../operations/sports_fixtures_sync.md) |

## Contesto

Un fantallenatore `UserType.AI` può già ricevere una rosa
(`assign_random_ai_roster`), ma **non esiste alcuna regola per schierarlo**.
Senza automazione una squadra IA arriva al lock senza formazione e non
contribuisce allo scontro diretto: il calendario H2H produce risultati falsati.

Il rischio opposto è più insidioso. Un'automazione che gira "quando serve"
rischia di usare informazioni che un umano non aveva al momento del proprio
lock — per esempio la distinta ufficiale pubblicata dopo. Sarebbe un vantaggio
competitivo invisibile e non dimostrabile a posteriori.

### Stato reale verificato

| Elemento | Stato |
| --- | --- |
| `Athlete.injured` | Esiste (`Boolean \| None`) |
| `PlayerMatchRating.fantasy_score` | Esiste, ma **solo per fixture passate** |
| `OfficialLineupEntry.is_starter` | Esiste (distinta ufficiale) |
| Motore di validazione (`evaluate_lineup`, moduli, panchina, lock) | Esiste, riusabile |
| `LineupSubmission.system_generated_ai` | **Assente** |
| Versione algoritmo / provenance / score candidati / motivi esclusione | **Assenti** |
| `OfficialLineup.fetched_at` | **Assente** — c'è solo `updated_at` da `TimestampMixin` |

## Decisione

### 1. Funzione obiettivo

Massimizzare il punteggio atteso della formazione, con una formula
**deterministica e versionata** (`ai_lineup_v1`). Per ogni calciatore
posseduto si calcola uno score:

```
score = w_disponibilita × disponibile
      + w_titolare      × titolare_ufficiale
      + w_forma         × forma_recente
```

con pesi costanti versionati insieme all'algoritmo. Si scelgono gli 11
titolari che massimizzano la somma degli score rispettando i vincoli di
modulo, più una panchina ordinata per score decrescente.

### 2. Segnali ammessi

Solo questi, in quest'ordine di affidabilità:

1. **Disponibilità** — `Athlete.injured`. Un infortunato è escluso, non
   penalizzato: schierarlo è un errore, non una scelta rischiosa.
2. **Titolarità ufficiale** — `OfficialLineupEntry.is_starter`, **solo** se
   ammessa dalla regola temporale del punto 4.
3. **Forma recente** — media di `PlayerMatchRating.fantasy_score` sulle ultime
   N giornate concluse della lega. Solo fixture **già terminate**.

Vietati: qualsiasi dato prodotto dopo l'istante di decisione, e qualsiasi
segnale non ricostruibile da queste tabelle.

### 3. Tie-break

A parità di score, in ordine: score più alto → maggior numero di presenze
recenti → `athlete_id` crescente. L'ultimo criterio garantisce che a parità
totale il risultato sia **stabile e riproducibile**, mai casuale.

### 4. Orario di decisione e uso della distinta ufficiale

La decisione è ancorata al **cutoff del turno** (`FantasyRound.cutoff_at`),
lo stesso istante che vincola gli umani. Il job può girare prima, ma valuta
solo dati la cui provenienza è **anteriore** all'istante di decisione.

La distinta ufficiale è utilizzabile solo se il suo timestamp di acquisizione
precede sia la decisione sia il lock del singolo calciatore
(`is_athlete_kickoff_locked`).

`OfficialLineup` non aveva un `fetched_at`: solo `updated_at`, che cambia a
ogni ri-sincronizzazione e quindi non è una prova affidabile dell'istante di
acquisizione. EP13-P05 **aggiunge `fetched_at`**, popolato dal sync: senza,
la regola "nessun dato post-lock" sarebbe indimostrabile a posteriori.

### 5. Dati provider mancanti

L'automazione **non salta mai il turno**. In ordine di degrado:

1. Distinta ufficiale assente → si usano solo disponibilità e forma.
2. Forma assente (inizio stagione) → si usano disponibilità e ruolo.
3. Tutto assente → si schiera una formazione **valida** per ruolo, ordinata
   per `athlete_id`, marcata `local_fallback`.

Una formazione valida ma mediocre è preferibile a nessuna formazione: senza,
lo scontro diretto è falsato per l'avversario umano.

### 6. Rispetto del lock progressivo

Dopo un lock progressivo i calciatori bloccati **non si toccano**. Eventuali
riottimizzazioni rispettano lo stesso limite di mosse tattiche degli umani
(`MAX_TACTICAL_MOVES = 3`) e usano il medesimo motore di validazione.

### 7. Perimetro di scrittura

Il servizio scrive **esclusivamente** su squadre la cui membership ha
`user.user_type == UserType.AI`, con lo stesso guard di
`assign_random_ai_roster` (`not_ai_manager`). Non tocca mai una formazione di
un utente manuale, nemmeno se vuota.

### 8. Tracciabilità

Ogni formazione automatica persiste: flag `system_generated_ai`, versione
algoritmo, timestamp di decisione, provenienza dei segnali usati, score dei
candidati, motivi di esclusione ed esito della validazione. Senza questi dati
la regola «nessun vantaggio post-lock» non è dimostrabile.

Realizzato con una **migrazione additiva** (`d6f9a3b1c247`) su
`lineup_submissions`: `system_generated_ai`, `ai_algorithm_version`,
`ai_decided_at` e `ai_decision_log` (JSONB con score, segnali e motivo di
esclusione per ogni candidato). Il log per-candidato sta in JSONB invece che in
una tabella dedicata: è scritto una volta e letto solo per audit, quindi non
giustifica il costo di una relazione a sé.

### 9. Esecuzione

Due percorsi, entrambi idempotenti:

* **Schedulato** — task Celery `fantasy_lineups.generate_ai`, beat ogni 30
  minuti (`AI_LINEUPS_AUTO_GENERATE_ENABLED`,
  `AI_LINEUPS_AUTO_GENERATE_INTERVAL_SECONDS`). Copre i turni `scheduled`/`open`
  delle leghe attive.
* **Amministrativo** — `POST /leagues/{id}/turni/{roundId}/formazioni-ia`
  (`league:admin`), con `dry_run=true` per la sola anteprima. Disponibile con
  parità su web e mobile.

Rieseguirli non produce effetti diversi: la formula è deterministica e il
servizio non tocca né le squadre umane né le formazioni già schierate a mano.

## Conseguenze

**Positive.** Le leghe con IA producono risultati H2H sensati. Il
determinismo rende ogni formazione riproducibile e contestabile. Il riuso del
motore di validazione umano impedisce che l'IA schieri formazioni illegali.

**Negative.** Serve una migrazione. La formula a pesi fissi è meno raffinata
di un modello, ma è verificabile — requisito esplicito della card, che vieta
un LLM che sceglie senza formula ispezionabile.

**Rischio accettato.** La qualità delle scelte dipende dalla copertura del
provider. All'inizio stagione, senza storico, le formazioni IA saranno vicine
al caso: accettabile, purché dichiarato nella UI.

## Decisioni risolte

1. **Provenienza della distinta ufficiale** → si aggiunge `fetched_at` a
   `OfficialLineup`, popolato dal sync. La regola anti-vantaggio diventa
   dimostrabile con una prova in tabella invece che con un'approssimazione.
2. **Partecipazione al pilot** → **le squadre IA partecipano al pilot reale**.
   L'automazione è quindi `Must` e **attiva in produzione**, senza
   feature-flag. Ne consegue che la qualità delle scelte deve essere
   accettabile fin dal primo turno e che ogni decisione dev'essere
   ispezionabile: è la ragione per cui il punto 8 (tracciabilità) non è
   opzionale.
3. **Pesi della formula** → `w_titolare = 2`, `w_forma = 1`, disponibilità
   come **filtro assoluto** (un infortunato è escluso, non penalizzato). A
   fantacalcio un titolare mediocre rende più di un fuoriclasse in panchina:
   la titolarità pesa doppio sulla forma.

## Alternative scartate

- **LLM che sceglie la formazione**: vietato dalla card (fuori scope, «LLM che
  sceglie senza formula verificabile»). Non riproducibile né contestabile.
- **Copiare l'ultima formazione**: semplice, ma ignora infortuni e
  indisponibilità; produce formazioni illegali dopo un cambio rosa.
- **Nessuna automazione**: lascia le squadre IA senza formazione e falsa gli
  scontri diretti degli avversari umani.
