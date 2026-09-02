# Piano di polling API-Football — EP00-04

| Metadato | Valore |
| --- | --- |
| Codice card | EP00-04 |
| Dipendenza | EP00-01 (matrice endpoint / ADR-0001) |
| Provider | API-Football v3 |
| Stimatore | [`tools/api_quota_estimator/`](../../tools/api_quota_estimator/) |
| Assunzioni | [`tools/api_quota_estimator/config/default.json`](../../tools/api_quota_estimator/config/default.json) |
| Scenari CSV | [`api_quota_scenarios.csv`](./api_quota_scenarios.csv) |
| Versione assunzioni | 1.0.0 |

## 1. Principio

Il consumo sportivo è **centrale** (modulo SPD). Una sola pipeline sincronizza i cinque campionati MVP; i client e il numero di utenti fantasy **non** moltiplicano le chiamate al provider (ADR-0001, FR-DAT-01).

Il fantavoto e i turni leggono snapshot normalizzati nel DB FantApperò, non l’API nel request path utente.

## 2. Finestre operative

| Finestra | Intervallo tipico | Obiettivo | Endpoint principali |
| --- | --- | --- | --- |
| **Catalog** | continuo / giornaliero | Anagrafiche, infortuni, trasferimenti, listone ammortizzato | `/leagues`, `/teams`, `/players`, `/players/squads`, `/injuries`, `/transfers`, `/standings`, `/status` |
| **Pre-partita** | T−6h → kickoff | Schedule, lineup, predizioni IA | `/fixtures` (batch league+date), `/fixtures/lineups`, `/predictions` |
| **Live** | kickoff → FT (+ buffer) | Stato e eventi scoring | `/fixtures?live=all`, `/fixtures/events` per `fixture_id` |
| **Post-partita** | FT → +2h | Chiusura timeline + stats Rating Beta | `/fixtures`, `/fixtures/events`, `/fixtures/players`, lineup catch-up |
| **Correzioni tardive** | fino a +72h | VAR / rettifiche provider (R-06) | re-fetch sparso events/players/fixtures |

Frequenze, durate e conteggi partite sono **tutti** in `config/default.json`.

## 3. Scenari dimensionati (default)

Simulazione ripetibile:

```bash
cd tools/api_quota_estimator
python -m api_quota_estimator --csv ../../docs/operations/api_quota_scenarios.csv
```

| Scenario | Partite live | Daily req | Monthly (×30) | Peak RPM |
| --- | --- | --- | --- | --- |
| **empty** | 0 | ~61 | ~1.8k | 0 |
| **average** (medio) | 8 | ~1.4k | ~43k | ~5 |
| **peak** (picco) | 45 | ~6.9k | ~206k | ~22 |
| **degraded** (picco degradato) | 45 | ~2.8k | ~83k | ~9 |

Valori esatti e breakdown per bucket: [`api_quota_scenarios.csv`](./api_quota_scenarios.csv).

`fantasy_users` in config è metadato operativo: al variare da 1 a 1e6 il calcolatore produce lo **stesso** consumo sportivo (test unitario).

### Mix mensile (opzionale)

`calendar.month_mix` (8 empty + 14 average + 8 peak) stima un mese calendario misto ≈ **8×peak + 14×average + 8×empty** richieste totali. Il report “monthly” per scenario è invece la proiezione pura `daily × days_per_month`.

## 4. Cache, batching, jitter, retry, budget RPM, circuit breaker

Definiti in `resilience` della config:

| Meccanismo | Comportamento |
| --- | --- |
| **Cache TTL** | Da 20s (events live) a 24h (leagues); rispetta `fetched_at` e ultimo dato buono |
| **Batching** | `/fixtures?live=all` e `/fixtures?league=&date=`; **no** multi-fixture su events/lineups/players |
| **Jitter** | fino al 15% dell’intervallo — sparge i picchi, non cambia il valor medio atteso |
| **Retry + backoff** | max 3 tentativi, base 1s ×2; amplificazione attesa **1.03** sul totale giornaliero |
| **Rate-limit budget** | target ≤ **70%** del RPM del piano (header `X-RateLimit-*`) |
| **Circuit breaker** | dopo 5 fallimenti / 429 persistenti: open 60s; solo probe half-open; niente cancellazione entità |

## 5. Quota quasi esaurita

Soglie su `x-ratelimit-requests-remaining / limit` (reset midnight UTC):

| Stato | Remaining | Azione |
| --- | --- | --- |
| **warn** | ≤ 25% | alert ops; sospendere refresh `criticality=low` |
| **degrade** | ≤ 15% | applicare `degraded_multipliers` (interval ×2.5, fixed polls ×0.5, catalog ×0.4); drop low; servire ultimo snapshot |
| **critical_only** | ≤ 5% | solo status batch + events/players per live / post-FT incompleti; breaker su catalog e segnali IA; omologazione in **Provvisorio** se stats incomplete |

Allineato ad ADR-0001 §6 (degradazione) e rischio R-07 della matrice EP00-01.

## 6. Quota minima consigliata

Formula (configurabile):

```text
quota_min = ceil(peak_daily × (1 + operational_margin))
```

Con default (`operational_margin=0.30`, sizing su **peak**):

| Voce | Valore |
| --- | --- |
| Peak daily | ~6 864 req/giorno |
| Margine operativo | 30% |
| **Quota minima consigliata** | **8 924 req/giorno** |
| Peak RPM stimato | ~22 (budget a 70% util → ~31 RPM) |
| **Piano consigliato** | **Ultra** (75 000/giorno, 450 RPM) |

Note:

- **Pro** (7 500/giorno) copre il picco grezzo ma **non** il margine del 30% → scartato dallo stimatore.
- RPM non è il vincolo dominante a queste frequenze; lo è la **quota giornaliera** nei weekend di picco.
- Alternative superiori: Mega (150 000/giorno).

Piani di riferimento pubblici API-Football (Free 100 / Pro 7 500 / Ultra 75 000 / Mega 150 000 req/giorno). Rivalidare prezzi e limiti sul sito vendor prima dell’acquisto.

## 7. Come ricalcolare

1. Modificare frequenze, partite o margine in `config/default.json`.
2. `python -m api_quota_estimator` (opzioni `--override`, `--csv`, `--json`).
3. Aggiornare questo documento e il CSV se le assunzioni di baseline cambiano.
4. Test: `python -m pytest` in `tools/api_quota_estimator` (empty / average / peak / utenti indipendenti).

## 8. Relazioni

- Matrice requisiti: [`../data/api_football_requirement_matrix.md`](../data/api_football_requirement_matrix.md)
- Confine provider: [`../adr/ADR-0001-sports-data-provider-boundary.md`](../adr/ADR-0001-sports-data-provider-boundary.md)
- Implementazione scheduler (EP04-06): [`sports_scheduler.md`](./sports_scheduler.md)
