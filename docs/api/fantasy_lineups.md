# Formazione, moduli, lock progressivo, panchina, tre mosse, copia, bozze e rinvii — EP06-02 / EP06-03 / EP06-04 / EP06-05 / EP06-06 / EP06-07

| Metadato | Valore |
| --- | --- |
| Card | EP06-02, EP06-03, EP06-04, EP06-05, EP06-06, EP06-07 |
| Modulo | `backend/src/fantasy_lineups/` |
| Dipendenze | EP04-05 (fixture/kickoff), EP05-05 (rosa P–D–C–A), EP06-01 (turno e cutoff) |
| FR | FR-FOR-01, FR-FOR-02 (tre mosse), FR-TUR-02 (lock per-calciatore), FR-SUB-01 (panchina e subentri) |

## Ruolo

Consente al fantallenatore di **schierare una formazione valida** per un turno europeo
aperto, scegliendo uno dei **sette moduli** e rispettando i vincoli **P–D–C–A**.

**EP06-03** applica il lock **progressivo per kickoff**: si bloccano solo i calciatori
la cui partita reale è già iniziata. I calciatori con kickoff futuro restano
modificabili. Il timestamp **server UTC** è autorevole; il client può validare in
anticipo ma il server resta decisivo.

**EP06-04** rende la **panchina ordinata** (priorità di ingresso) e definisce il motore
di **fino a 5 sostituzioni automatiche**: un panchinaro con voto subentra al primo
titolare **dello stesso ruolo** senza voto, camminando l'ordine di panchina. Il modulo
resta valido perché il cambio è sempre a parità di ruolo. I minuti/voti reali restano
un input del motore: la risoluzione dopo i dati finali è **EP07-04**.

**EP06-05** registra le **tre mosse tattiche** del turno. Dopo la formazione iniziale,
ogni salvataggio confermato che modifica slot o ordine di panchina **nella finestra
progressiva** (almeno un calciatore già bloccato al kickoff) consuma **una** mossa.
Il quarto tentativo è rifiutato. Le sostituzioni automatiche **non** consumano mosse.
Nessuna mossa è retroattiva: i calciatori bloccati non cambiano slot né posizione in
panchina. Una conferma composta (modulo + cambi sbloccati) vale **una** mossa.

Il motore regole puro (`fantasy_lineups/rules.py` + `@fantappero/contracts` `fantasyLineups`)
è condiviso tra API e UI.

**EP06-06** consente di **copiare la formazione precedente** e di **salvare una bozza**.
La copia è sempre rivalidata contro la rosa corrente e la disponibilità al kickoff
(UTC; kickoff simultanei, anche espressi in fusi diversi, si bloccano insieme).
I calciatori usciti dalla rosa vengono esclusi; quelli già locked non possono
diventare nuovi titolari. Il salvataggio bozza può essere incompleto e **non**
consuma mosse tattiche. Il server rifiuta copia e bozza fuori tempo (turno non
aperto o tentativo sui calciatori bloccati).

**EP06-07** ricalcola cutoff e lock quando una partita è rinviata o cambia orario.
Un rinvio **dopo** il kickoff già trascorso non sblocca il calciatore e non
rimborsa mosse tattiche. Un rinvio **prima** del fischio lascia il calciatore
modificabile e può slittare il cutoff. Kickoff simultanei, anche espressi in fusi
diversi, si confrontano in UTC.

Fuori scope: formazione effettiva persistita dopo i voti (EP07-04).

La formazione è agganciata al **turno europeo** `(round_id, fantasy_team_id)`, non allo
scontro H2H: i matchup di calendario restano un dominio distinto.

## Moduli approvati

| Modulo | P | D | C | A |
| --- | --- | --- | --- | --- |
| 3-4-3 | 1 | 3 | 4 | 3 |
| 3-5-2 | 1 | 3 | 5 | 2 |
| 4-3-3 | 1 | 4 | 3 | 3 |
| 4-4-2 | 1 | 4 | 4 | 2 |
| 4-5-1 | 1 | 4 | 5 | 1 |
| 5-3-2 | 1 | 5 | 3 | 2 |
| 5-4-1 | 1 | 5 | 4 | 1 |

Regole: esattamente 11 titolari, un portiere titolare, panchina = resto della rosa
nell'ordine scelto, nessun duplicato, solo calciatori della propria rosa con ruolo
listone risolvibile. Rosa **Convalidata** obbligatoria.

## Cutoff di turno e lock per-calciatore

Il cutoff del turno resta il **primo kickoff** delle fixture attive (kickoff
simultanei → stesso istante). Non congela più l'intera formazione.

| Condizione | Effetto |
| --- | --- |
| Turno `scheduled` | Nessun salvataggio (`turn_not_open`) |
| Turno `skipped` | Nessun salvataggio (`turn_skipped`) |
| Turno `open` o `locked` | Salvataggio ammesso se i calciatori bloccati non cambiano slot né ordine di panchina |
| `now >= kickoff_at` (UTC) o status live/FT | Calciatore **bloccato** (`starter`/`bench` e posizione in panchina congelati) |
| Kickoff futuro, PST/CANC **prima** del kickoff originale, nessuna fixture nel turno | Calciatore **modificabile** |
| PST/CANC o orario spostato in avanti **dopo** `lock_latched_at` | Calciatore **resta bloccato** (nessun vantaggio retroattivo) |
| Prima formazione e calciatore già locked | Non può essere schierato titolare |

I panchinari bloccati sono **barriere**: gli altri non possono scavalcarli nell'ordine
e i nuovi panchinari restano dopo tutti i locked. Così non si ottiene un vantaggio
retroattivo dopo il fischio d'inizio. Kickoff simultanei (anche espressi in fusi
diversi, confrontati in UTC) si bloccano insieme.

Il club del calciatore si risolve da `role_assignments.club_id` (fallback
`squad_memberships` attive della stagione) e si abbina alla fixture attiva del
turno in cui quel club è casa o trasferta.

## Panchina e sostituzioni automatiche

Costante condivisa: `MAX_AUTOMATIC_SUBSTITUTIONS = 5`.

Algoritmo puro `resolveAutomaticSubstitutions` / `resolve_automatic_substitutions`:

1. Si percorre la panchina **nell'ordine salvato**.
2. Un panchinaro presente in `playedAthleteIds` (ha il voto) cerca il primo titolare
   dello **stesso ruolo** assente da quel set e non ancora sostituito.
3. Si applicano al massimo 5 cambi. Il sesto e successivi restano in panchina.
4. Un portiere entra solo al posto di un portiere; stesso vincolo per D/C/A.
5. Il modulo dell'XI effettivo resta quello schierato (cambio same-role).

Nessun fallback cross-ruolo in questa card.

## Tre mosse tattiche

Costante condivisa: `MAX_TACTICAL_MOVES = 3`.

Una **mossa** è un salvataggio confermato che cambia modulo, titolari o ordine di
panchina **dopo** che esiste una formazione iniziale e **almeno un** calciatore della
rosa è bloccato al kickoff. Kickoff simultanei (anche espressi in fusi diversi,
confrontati in UTC) aprono la finestra insieme.

| Condizione | Consuma mossa |
| --- | --- |
| Prima formazione (nessun salvataggio precedente) | No |
| Tutti i calciatori ancora sbloccati | No (formazione iniziale, FR-FOR-01) |
| Salvataggio identico alla versione corrente | No |
| Salvataggio con calciatori sbloccati dopo il primo lock | Sì (1), anche se composto |
| Sostituzioni automatiche (EP06-04) | No |
| Quarto salvataggio che cambierebbe la formazione | Rifiuto `tactical_moves_exhausted` |
| Tentativo su calciatore bloccato | Rifiuto `athlete_kickoff_locked` / `bench_order_locked` (nessun consumo) |

Ogni mossa applicata conserva `from_payload` / `to_payload` (modulo e liste), autore,
istante UTC e `sequence` 1–3.

## Entità

| Tabella | Vincoli | Note |
| --- | --- | --- |
| `lineup_submissions` | unique `(round_id, fantasy_team_id)`; `revision >= 1` | Una formazione corrente per squadra e turno |
| `lineup_players` | unique `(submission_id, athlete_id)`; unique `(submission_id, slot_kind, sort_order)` | `starter` / `bench`; `sort_order` sulla panchina è la priorità di subentro |
| `tactical_moves` | unique `(submission_id, sequence)`; `sequence` 1–3 | Uso e validità temporale; `status=applied` |
| `lineup_drafts` | unique `(round_id, fantasy_team_id)` | Bozza incompleta; JSONB titolari/panchina; `copy_source_round_id` opzionale |

Ogni salvataggio è atomico: sostituisce i giocatori, incrementa `revision` (salvo no-op
identico), scrive audit `fantasy_lineup_saved` e, se consuma una mossa, inserisce
`tactical_moves` + audit `fantasy_tactical_move_applied`. Il lock per-calciatore
si deriva dal clock server, dallo stato fixture e da `lock_latched_at` persistito
sul link turno–partita: un rinvio o un cambio orario dopo il fischio non sblocca
il calciatore né rimborsa mosse.

## API

| Metodo | Percorso | Permesso |
| --- | --- | --- |
| `GET` | `/leagues/{id}/turni/{roundId}/formazione` | `roster:view` |
| `PUT` | `/leagues/{id}/turni/{roundId}/formazione` | `roster:edit` |
| `POST` | `/leagues/{id}/turni/{roundId}/formazione/copia` | `roster:edit` |
| `PUT` | `/leagues/{id}/turni/{roundId}/formazione/bozza` | `roster:edit` |

Il contesto include `serverNow`, `modificationAllowed` (turno editabile e almeno un
calciatore sbloccato), `maxAutomaticSubstitutions`, `maxTacticalMoves`,
`tacticalMovesUsed`, `tacticalMovesRemaining`, `tacticalMoves`, `previousLineup`,
`draft`, `copyAvailable`, `copyIssues` e, per ogni elemento di
`roster`: `locked`, `lockLatched`, `kickoffAt`, `fixtureStatus`.

Body salvataggio:

```json
{
  "module": "4-3-3",
  "starterAthleteIds": ["…11 uuid…"],
  "benchAthleteIds": ["…resto rosa, in ordine di subentro…"]
}
```

Errori con motivazione: `invalid_module`, `module_role_mismatch`,
`goalkeeper_count_invalid`, `starter_count_invalid`, `duplicate_athlete`,
`athlete_not_in_roster`, `bench_incomplete`, `unresolved_role`,
`roster_not_validated`, `turn_not_open`, `turn_skipped`,
`turn_modification_closed`, `athlete_kickoff_locked`, `bench_order_locked`,
`tactical_moves_exhausted`, `previous_lineup_not_found`,
`copied_athlete_not_in_roster`, `copied_athlete_unavailable`.

La **copia** prende l'ultima formazione confermata di un turno precedente della
stessa squadra, la rivalida e la scrive in **bozza**. Non conferma e non consuma
mosse. La **bozza** accetta uno schieramento incompleto; duplicati, calciatori
fuori rosa e modifiche a calciatori locked restano rifiutati. La conferma
(`PUT .../formazione`) cancella la bozza del turno.

## UI

- Web `/formazione` e Mobile tab Formazione: scelta turno, modulo, titolari per ruolo,
  panchina **riordinabile** (menu ordine di ingresso), badge **bloccato** sugli slot e sulle posizioni
  con partita iniziata, **contatore mosse** e anteprima del consumo, **copia formazione precedente**,
  **salva bozza**, salvataggio confermato. Stati
  caricamento / vuoto / errore / successo / permessi insufficienti.
- Cambio modulo: i titolari locked restano nello slot del proprio ruolo.
- Validazione preventiva nel client con lo stesso motore; il server resta decisivo.

## Metriche e audit

- Metrica: `fantasy_lineup_saved_total{result}` (`success`, `athlete_kickoff_locked`, `bench_order_locked`, `tactical_moves_exhausted`, …)
- Metrica: `fantasy_lineup_copied_total{result}`
- Metrica: `fantasy_lineup_draft_saved_total{result}`
- Metrica: `fantasy_tactical_move_applied_total`
- Audit: `fantasy_lineup_saved` (round, team, modulo, revision; niente PII)
- Audit: `fantasy_lineup_copied` (round, team, sourceRoundId, dropped/unavailable count; niente PII)
- Audit: `fantasy_lineup_draft_saved` (round, team, modulo; niente PII)
- Audit: `fantasy_tactical_move_applied` (sequence, revision, moduli; niente PII)

## Verifica

```bash
docker compose --env-file infra/local/.env.example build api
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/fantasy_turns tests/integration/fantasy_turns tests/unit/fantasy_lineups tests/integration/fantasy_lineups -ra'

docker compose --env-file infra/local/.env.example run --rm web \
  pnpm --filter @fantappero/contracts test
docker compose --env-file infra/local/.env.example run --rm web \
  pnpm --filter @fantappero/web test -- src/pages/MatchdayPage.test.tsx src/pages/FormationPage.test.tsx
```
