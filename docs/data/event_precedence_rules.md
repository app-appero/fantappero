# Regole di precedenza eventi fantavoto (EP00-03)

| Metadato | Valore |
| --- | --- |
| Card | EP00-03 |
| Dipendenza | EP00-02 (corpus `backend/tests/fixtures/api_football/`) |
| Implementazione | `backend/src/sports_data/normalization/` |
| ADR | [`../adr/ADR-0002-sports-event-precedence.md`](../adr/ADR-0002-sports-event-precedence.md) |
| Scope | Normalizzazione deterministica **senza** applicazione dei delta fantavoto |

## 1. Principio

Ogni esito è **ripetibile**: stessi payload → stessi `provider_event_key`, stessi `kind` / `status` / `anomaly_codes`.

Contraddizioni e dati insufficienti **non** vengono risolti in silenzio: compaiono come `status=provisional|anomaly|insufficient` e/o `NormalizationResult.anomalies`.

Gol e assist **non** si duplicano tra `/fixtures/events` e `/fixtures/players`: gli eventi sono primari; le stats sono **watchdog**.

## 2. Tipi interni (`ScoringEventKind`)

| Kind | Semantica prodotto | Fonte primaria |
| --- | --- | --- |
| `goal` | Gol da gioco (`Normal Goal`) | events |
| `penalty_scored` | Rigore segnato (`Penalty`) | events |
| `own_goal` | Autogol (`Own Goal`) | events |
| `assist` | Assist (campo `assist.id` su gol) | events |
| `penalty_missed` | Rigore sbagliato **e parato** (tiratore) | events (+ stats) |
| `penalty_saved` | Rigore parato (portiere) | **players** (`penalty.saved`) |
| `penalty_off_target` | Rigore non in porta (tiratore, senza save) | events |
| `unknown` | `type=Goal` con `detail` non riconosciuto | events → `insufficient` |

> Nota: in fantavoto, sia `penalty_missed` sia `penalty_off_target` sono candidati al malus tiratore (−3); `penalty_saved` è il bonus portiere (+3). I punti restano fuori da EP00-03.

## 3. Precedenza per famiglia

### 3.1 Gol e rigore segnato

1. Emmettere un evento interno per ogni riga events con `detail ∈ {Normal Goal, Penalty}`.
2. **Non** creare gol aggiuntivi da `players.goals.total` / `penalty.scored`.
3. Se i conteggi divergano → `goal_count_mismatch` / `penalty_scored_mismatch` (e `stats_only_goal` se stats > events).

### 3.2 Assist

1. Emmettere `assist` separato quando `assist.id` è valorizzato su un gol (`Normal Goal`; non su Penalty/Own Goal/Missed).
2. **Non** inventare assist da `players.goals.assists`.
3. Divergenza di conteggio → `assist_count_mismatch` (+ `stats_only_assist` se stats > events).

### 3.3 Autogol

1. Solo `detail=Own Goal` → `own_goal`.
2. Non usare `goals.total` del giocatore (nel corpus OG il totale resta `null`).
3. `team_id` è quello dell’evento provider (spesso la squadra **beneficiata**); documentato in `notes`.

### 3.4 Rigore sbagliato / parato / non in porta

Nel corpus EP00-02:

- `Missed Penalty` in events è **raro** (1/20).
- `penalty.missed` + `penalty.saved` in stats coesistono spesso **senza** evento Missed Penalty.
- Non esiste un `detail` events per “parato”.

Algoritmo:

1. Raccogliere miss da events (`Missed Penalty`), poi miss residui da `penalty.missed` (stats-only → anomalia `events_missing_missed_penalty`).
2. Raccogliere save da `penalty.saved` (GK).
3. Accoppiare miss↔save preferendo team opposti; ordine deterministico.
4. **Miss + save** → `penalty_missed` (tiratore) + `penalty_saved` (portiere).  
   - Con evento Missed → `confirmed`.  
   - Solo stats → `provisional` + `events_missing_missed_penalty`.
5. **Miss senza save**:
   - Da events → `penalty_off_target` `confirmed`.
   - Solo stats → `penalty_off_target` `provisional` + `orphan_penalty_miss` (non si assume certezza off-target).
6. **Save senza miss** → `penalty_saved` `insufficient` + `orphan_penalty_save`.

## 4. `provider_event_key`

Composizione (nessun id evento provider stabile — OQ-06):

```text
events|{fixture}|{elapsed}|{extra}|{type}|{detail}|{player_id}|{assist_id}|{role}
players|{fixture}|{kind}|{player_id}|{ordinal}
```

`role` distingue `goal` / `assist` / `penalty_scored` / `own_goal` / `penalty_miss` / `unknown` derivati dalla stessa riga events. Gli esiti miss aggiungono `|outcome=saved|off_target`.

## 5. Stati

| Status | Quando |
| --- | --- |
| `confirmed` | Fonte primaria presente e coerenza sufficiente |
| `provisional` | Esito usabile ma incompleto (es. miss solo in stats) |
| `anomaly` | Riservato a conflitti hard su singolo evento (watchdog di fixture vivono in `result.anomalies`) |
| `insufficient` | Manca player id, detail sconosciuto, save orfano |

## 6. Casi campione (corpus)

| Fixture | Esito documentato |
| --- | --- |
| `718611` | `own_goal` (Poussin) + `penalty_scored` + miss/save stats-only → `provisional` |
| `1038042` | `Missed Penalty` + `penalty.saved` → `penalty_missed` + `penalty_saved` `confirmed`; + `penalty_scored` |
| `1388315` | gol + assist da events; penalty scored; miss/save stats-only → `provisional` |
| `1035055` | miss/save solo stats (Fernández / Aréola) → `provisional` |

## 7. Non-scope

- Motore di scoring / omologazione.
- Cartellini, sostituzioni, VAR (fuori dai kind fantavoto di questa card, salvo estensioni future).
- Rating Beta / minuti.
