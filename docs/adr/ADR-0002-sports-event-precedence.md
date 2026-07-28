# ADR-0002 — Precedenza eventi sportivi per il fantavoto

| Metadato | Valore |
| --- | --- |
| Stato | Accettato (baseline EP00-03) |
| Data | 2026-07-27 |
| Card | EP00-03 |
| Dipendenza | EP00-02; ADR-0001 |
| Relazioni | [`../data/event_precedence_rules.md`](../data/event_precedence_rules.md); matrice [`../data/api_football_requirement_matrix.md`](../data/api_football_requirement_matrix.md); OQ [`../data/api_football_open_questions.md`](../data/api_football_open_questions.md) |

## Contesto

Il fantavoto applica bonus/malus (gol, assist, autogol, rigori) su dati API-Football che arrivano da due endpoint distinti:

- `/fixtures/events` — timeline tipizzata (`type`/`detail`)
- `/fixtures/players` — aggregati per giocatore (`goals.*`, `penalty.*`)

Sul corpus congelato EP00-02 i conteggi gol/assist coincidono, ma i rigori sbagliati/parati sono spesso **solo nelle stats**, senza `Missed Penalty` in events. Non esiste un `detail` events per “rigore parato”. Senza una regola di precedenza esplicita, il motore di scoring rischierebbe doppi conteggi o fusioni silenziose.

## Decisione

1. **Events primari** per: `goal`, `penalty_scored`, `own_goal`, `assist`, e per il miss quando `detail=Missed Penalty` è presente.
2. **Players primari** per: `penalty_saved` (`penalty.saved` sul portiere).
3. **No duplicazione**: stats non inventano gol/assist già rappresentabili da events; servono da watchdog (mismatch → anomalie di fixture).
4. **Classificazione rigori** tramite accoppiamento deterministico miss↔save (vedi regole); esiti incompleti restano `provisional` / `insufficient` con `AnomalyCode` esplicito.
5. **Chiave idempotente** `provider_event_key` composta (fixture + tempo + type/detail + player/assist + role / stats ordinal) — il provider non espone un id evento stabile.
6. **SPD** espone solo entità normalizzate (`NormalizedScoringEvent`); i delta fantavoto restano a un motore successivo.

## Conseguenze

### Positive

- Esiti ripetibili e testabili offline sul corpus.
- Conflitti visibili (Provvisorio / anomalia) allineati a FR-DAT-01 e R-06.
- Autogol non confondibile con gol (`Own Goal` ≠ `goals.total`).

### Negative / costi

- Miss solo-stats restano provisional finché events non li espongono.
- Accoppiamento miss/save per team è euristico se ci sono più miss nella stessa partita (ordine deterministico, non “silenzioso”).
- Off-target puro assente nel corpus: coperto da test sintetici.

## Alternative scartate

| Alternativa | Perché scartata |
| --- | --- |
| Stats sempre primarie per bonus | Perde timeline e `Own Goal`/`Missed Penalty`; diverge dalla matrice §3.6 |
| Unire silenziosamente miss+save | Viola accettazione EP00-03 (no risoluzione silenziosa) |
| Ignorare `penalty.saved` | Gap bloccante G-03 / OQ-04 |

## Chiusure OQ collegate (parziali)

| OQ | Esito in EP00-03 |
| --- | --- |
| OQ-02 Autogol | Chiuso operativamente: solo `Own Goal` → `own_goal` |
| OQ-03 Assist | Chiuso: events primari, stats watchdog |
| OQ-04 Rigore parato | Chiuso: `players.penalty.saved` primario |
| OQ-05 Missed | Chiuso per classificazione tiratore; yellow-red resta aperto (fuori kind di questa ADR) |
| OQ-06 Chiave | Chiuso: composizione documentata + test idempotenza |

## Compliance checklist

- [x] Nessun doppio gol/assist events↔stats
- [x] Distinzione assist / autogol / rigore segnato / sbagliato-parato / non in porta / unknown
- [x] Anomalie esplicite
- [x] Test parametrizzati su payload campione + casi sintetici
- [x] Nessun motore di scoring in questo ADR
