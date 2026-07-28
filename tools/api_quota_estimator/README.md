# API quota estimator (EP00-04)

Stimatore ripetibile del consumo **API-Football v3** per il sync centrale SPD.
Le chiamate **non** scalano con il numero di utenti fantasy (`fantasy_users` è solo metadato).

## Quick start

```bash
cd tools/api_quota_estimator
python -m api_quota_estimator
python -m api_quota_estimator --csv ../../docs/operations/api_quota_scenarios.csv
python -m pytest
```

Override assunzioni senza toccare il file:

```bash
python -m api_quota_estimator --override "{\"scenarios\":{\"peak\":{\"matches_live\":50}}}"
```

## Layout

| Percorso | Ruolo |
| --- | --- |
| `config/default.json` | Tutte le assunzioni modificabili |
| `api_quota_estimator/` | Calcolatore + CLI |
| `tests/` | Scenario empty / average / peak + indipendenza utenti |

## Output

- Report testuale: daily/monthly per `average`, `peak`, `degraded` (+ `empty`)
- CSV scenari: `docs/operations/api_quota_scenarios.csv`
- Piano consigliato con margine operativo

Documentazione operativa: [`docs/operations/api_football_polling_plan.md`](../../docs/operations/api_football_polling_plan.md).
