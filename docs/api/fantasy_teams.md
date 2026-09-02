# Squadre fantasy, rosa, crediti, import CSV, composizione e storico — EP05-01 … EP05-06

| Metadato | Valore |
| --- | --- |
| Card | EP05-01, EP05-02, EP05-03, EP05-04, EP05-05, EP05-06 |
| Modulo | `backend/src/fantasy_teams/` |
| Dipendenze | EP03-05 (lifecycle lega), EP04-04 (listone / athletes) |

## Ruolo

Persiste una **squadra fantasy per partecipante** con slot rosa fissi e **esclusività di lega**.
Il **saldo crediti** è ricostruibile da un **ledger append-only** con causali: nessun aggiornamento
diretto opaco del saldo.

Ogni partecipante con `roster:edit` può **assegnare/liberare** calciatori **sulla propria rosa**,
indicando il **credito di acquisto**. L’admin può farlo su **qualsiasi** squadra e registrare
aggiustamenti crediti manuali, oppure **importare rose da CSV** con anteprima e conferma atomica.

**EP05-05** applica i limiti di composizione **configurabili** da `league_rules`
(Standard MVP: 35 = 3P–11D–11C–10A), la diversità campionati (≥3) e lo stato **Convalidata**.
Rosa incompleta ammessa in asta; obbligatoria completa all’avvio stagione (`auction → active`).

**EP05-06** conserva **intervalli di possesso** append-only e **snapshot immutabili per numero di turno**,
così un risultato storico resta ricostruibile dopo rilasci, mercato o trasferimenti successivi.
Il modulo turni europei (EP06) non è anticipato: lo snapshot usa un `roundNumber` intero.

Fuori scope: mercato/asta/scambi, scoring.
I turni europei vivono in [`fantasy_turns.md`](./fantasy_turns.md) (EP06-01).
La formazione per turno vive in [`fantasy_lineups.md`](./fantasy_lineups.md) (EP06-02).

## Entità

| Tabella | Vincoli | Note |
| --- | --- | --- |
| `fantasy_teams` | 1:1 su `membership_id`; `composition_status` ∈ incomplete/invalid/validated | `validated_at` quando Convalidata |
| `fantasy_roster_slots` | unique `(fantasy_team_id, slot_index)`; unique parziale `(league_id, athlete_id)` dove assegnato; `purchase_credits >= 0` se presente | Stato corrente; slot vuoti alla nascita squadra |
| `credit_accounts` | 1:1 su `fantasy_team_id`; `balance >= 0`; `version` optimistic | Saldo aggiornato solo via ledger |
| `credit_ledger_entries` | unique `(account_id, transaction_id)`; append-only | Causali: `initial_allocation`, `admin_adjustment`, `roster_purchase`, `roster_release_refund` |
| `roster_import_sessions` | status `draft`/`confirmed`; payload anteprima JSONB | Nessuna scrittura rosa/crediti in draft |
| `roster_ownership_intervals` | unique parziale attivo `(league_id, athlete_id)` e `(fantasy_team_id, slot_index)`; `released_at IS NULL OR >= acquired_at` | Append-only; `source` ∈ manual/csv_import/admin |
| `roster_turn_snapshots` | unique `(league_id, round_number)`; `round_number >= 1` | Immutabile dopo creazione; idempotente |
| `roster_turn_snapshot_entries` | unique `(snapshot_id, fantasy_team_id, slot_index)` | Slot pieni al momento dello snapshot |

Alla creazione squadra (o backfill migrazione) viene registrata l'allocazione iniziale pari a
`league_rules.total_credits`. Assegnazione con `purchaseCredits > 0` addebita il ledger;
rilascio rimborsa l’eventuale credito di acquisto e **chiude** l’intervallo di possesso.

## Storico rosa e snapshot (EP05-06)

| Contesto | Comportamento |
| --- | --- |
| Assign / CSV | Apre (o aggiorna prezzo) intervallo; se sostituisce, chiude il precedente nella stessa TX |
| Release | Imposta `released_at` sull’intervallo attivo |
| As-of | Ricostruisce la rosa con `acquired_at <= t AND (released_at IS NULL OR released_at > t)` |
| Snapshot turno | Congela gli slot pieni correnti; sopravvive a release successivi |
| Calendario H2H | Se presente, `roundNumber` non può superare `round_count`; altrimenti solo `>= 1` |

## Composizione rosa (EP05-05 / FR-ROS-02)

Validazione lato server su ruoli effettivi del listone (override lega inclusi):

| Contesto | Regola |
| --- | --- |
| Durante asta (`draft`/`configuring`/`auction`) | Incompleta ammessa; **non** si può superare il tetto per ruolo |
| Avvio stagione (`auction → active`) | Rosa completa: totale e conteggi P–D–C–A esatti + ≥3 campionati rappresentati |
| Assegnazione / CSV | Rifiuta `role_quota_exceeded` e `role_unresolved` |

Lo stato `validated` aggiorna `composition_status` / `validated_at` e produce audit
`fantasy_roster_composition_validated`. La risposta `GET …/rosa` include `composition` con
conteggi, limiti, errori aggregati e stato.

I blocker lifecycle `fantasy_teams_not_configured` / `credits_not_configured` non sono più
placeholder: verificano rose e conti reali.

## API

| Metodo | Percorso | Permesso |
| --- | --- | --- |
| `GET` | `/leagues/{id}/rosa` | `roster:view` — rosa del chiamante (creazione lazy) + composizione |
| `GET` | `/leagues/{id}/squadre` | `roster:view` — elenco squadre (`compositionStatus`) |
| `GET` | `/leagues/{id}/occupazione-rosa` | `roster:view` — mappa atleta→squadra per UI listone |
| `GET` | `/leagues/{id}/squadre/{teamId}/giocatori` | `roster:view` — rosa corrente di una squadra (scambi) |
| `GET` | `/leagues/{id}/crediti` | `roster:view` — saldo + `reconstructedBalance` |
| `GET` | `/leagues/{id}/crediti/movimenti` | `roster:view` — ledger immutabile |
| `GET` | `/leagues/{id}/rosa/storico` | `roster:view` — intervalli possesso (`activeOnly` opzionale) |
| `GET` | `/leagues/{id}/rosa/as-of?at=` | `roster:view` — ricostruzione rosa a timestamp UTC |
| `GET` | `/leagues/{id}/rosa/snapshot-turni` | `roster:view` — elenco snapshot |
| `GET` | `/leagues/{id}/rosa/snapshot-turni/{roundNumber}` | `roster:view` — dettaglio (`teamId` opzionale) |
| `POST` | `/leagues/{id}/amministrazione/rosa/snapshot-turni` | `league:admin` — crea snapshot idempotente (`roundNumber`) |
| `GET` | `/leagues/{id}/amministrazione/squadre/{teamId}/rosa/storico` | `league:admin` |
| `POST` | `/leagues/{id}/amministrazione/crediti/movimenti` | `league:admin` — aggiustamento idempotente (`transactionId`) |
| `POST` | `/leagues/{id}/amministrazione/squadre` | `league:admin` — assicura squadra+slot+conto per ogni iscritto |
| `POST` | `/leagues/{id}/amministrazione/squadre/{teamId}/rosa/random` | `league:admin` — riempie slot vuoti di un fantallenatore IA con calciatori liberi random |
| `GET` | `/leagues/{id}/amministrazione/squadre/{teamId}` | `league:admin` — dettaglio rosa per inserimento multi-squadra |
| `GET` | `/leagues/{id}/amministrazione/squadre/{teamId}/crediti` | `league:admin` — saldo + ledger di una squadra |
| `PUT` | `/leagues/{id}/amministrazione/squadre/{teamId}/slot/{slotIndex}` | `roster:edit` — assegna calciatore (`athleteId`, `purchaseCredits`); solo propria squadra se non admin |
| `DELETE` | `/leagues/{id}/amministrazione/squadre/{teamId}/slot/{slotIndex}` | `roster:edit` — libera slot (+ rimborso); solo propria squadra se non admin |
| `GET` | `/leagues/{id}/amministrazione/import-csv/modello` | `league:admin` — template CSV ufficiale |
| `POST` | `/leagues/{id}/amministrazione/import-csv/anteprima` | `league:admin` — upload multipart, anteprima senza write |
| `POST` | `/leagues/{id}/amministrazione/import-csv/anteprima-testo` | `league:admin` — stesso flusso con testo JSON (`csvText`) |
| `POST` | `/leagues/{id}/amministrazione/import-csv/{importId}/conferma` | `league:admin` — applica atomico; idempotente se già confirmed |

### CSV (EP05-04 / FR-ROS-03)

Colonne: `squadra,provider_id,nome,crediti`.

Matching: `provider_id` prioritario; `nome` solo se univoco; ambiguità → status `ambiguous` + candidati
(risolvibili in conferma via `resolutions: [{rowNumber, athleteId}]`).

Vincoli server (stessi dell’inserimento manuale): esclusività lega, crediti ≥ 0, saldo non negativo,
slot liberi, tetti ruolo P–D–C–A. Diversità campionati e completezza valgono all’avvio stagione.

Conferma: un solo evento audit `fantasy_roster_csv_imported`; nessuna scrittura rosa/crediti in anteprima.

## UI

- Web `/rosa` e Mobile tab Rosa: inserimento manuale, crediti, composizione P/D/C/A, «Assicura squadre».
- Sezione **Storico**: intervalli di possesso e snapshot per turno; admin può creare snapshot.
- **Import CSV (EP05-04):** API e codice UI presenti; pannello **temporaneamente nascosto**
  (`SHOW_ROSTER_CSV_IMPORT = false` in `RosterPage` / `RosterScreen`). Riattivare da lì quando
  il flusso (es. esporre `providerId` in listone) sarà chiarito.

## Metriche e audit

- Metriche: `fantasy_roster_ownership_total{result}`, `fantasy_roster_snapshot_total{result}`.
- Audit: `fantasy_roster_ownership_closed`, `fantasy_roster_turn_snapshot_created`.

## Verifica

```bash
docker compose --env-file infra/local/.env.example run --rm api \
  python -m alembic upgrade head

docker compose --env-file infra/local/.env.example --profile test run --rm api \
  sh -lc 'DATABASE_URL="$TEST_DATABASE_URL" python -m pytest tests/unit/fantasy_teams tests/integration/fantasy_teams -ra'
```
