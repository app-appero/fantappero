# Rating Beta sperimentale (EP00-05)

Prototipo **offline** del voto statistico FantApperò: formula versionata per P/D/C/A,
soglia minuti Standard 15, gol/assist esclusi dal voto, report per ruolo.
Non scrive nel database applicativo.

## Quick start

```bash
cd experiments/rating_beta
python -m rating_beta
python -m pytest
```

Config di default: [`config/beta-v0.1.yaml`](config/beta-v0.1.yaml)  
Report: [`reports/rating_beta_v0.1.md`](reports/rating_beta_v0.1.md)  
Corpus: `backend/tests/fixtures/api_football/` (EP00-02)

## Layout

| Percorso | Ruolo |
| --- | --- |
| `rating_beta/` | Formula, eleggibilità, report |
| `config/beta-v0.1.yaml` | Coefficienti e soglie versionati |
| `tests/` | Golden + soglia/clamp/no-doppio-premio |
| `reports/rating_beta_v0.1.md` | Statistiche per ruolo |

## Regole v0.1

- `raw = clamp(base + Σ contributi, 3, 10)` con `base=6`
- `display` = arrotondamento a scatti di 0,5 (solo se eleggibile)
- sotto 15' → voto solo con evento rilevante (gol, assist, rigore sbagliato, autogol, rosso); portiere titolare sempre eleggibile se ha minuti
- `goals.total` / `goals.assists` mai usati come componenti
- `games.rating` solo confronto diagnostico nel report
