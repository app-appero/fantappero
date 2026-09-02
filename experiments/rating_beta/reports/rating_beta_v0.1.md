# Rating Beta report — beta-v0.1

| Metadato | Valore |
| --- | --- |
| Card | EP00-05 |
| Formula | `beta-v0.1` |
| Generato | 2026-07-27T15:28:55Z |
| Corpus | backend/tests/fixtures/api_football |
| Base | 6.0 |
| Clamp | 3.0–10.0 |
| Display step | 0.5 |
| Soglia minuti | 15 |
| Voti eleggibili | 523 / 694 |

## Controlli di design

- Gol e assist **non** entrano nel voto statistico (solo flag di eleggibilità sotto soglia).
- `games.rating` provider è riportato solo come **diagnostica** (media scarto assoluto per ruolo).
- Il prototipo **non** scrive risultati ufficiali nel database applicativo.
- Ogni voto eleggibile è ricostruibile come `clamp(base + Σ componenti)`.

## Statistiche per ruolo (valore grezzo `raw`)

| Ruolo | n | media | mediana | σ | p10 | p25 | p75 | p90 | min | max | non eleggibili | mean abs Δ vs provider |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P | 41 | 6.663 | 6.628 | 0.364 | 6.252 | 6.404 | 6.816 | 7.108 | 6.088 | 7.744 | 26 | 0.500 |
| D | 170 | 7.078 | 7.003 | 0.353 | 6.711 | 6.828 | 7.314 | 7.605 | 6.000 | 7.864 | 55 | 0.428 |
| C | 188 | 7.035 | 7.024 | 0.366 | 6.646 | 6.788 | 7.232 | 7.470 | 5.800 | 8.392 | 57 | 0.380 |
| A | 124 | 6.672 | 6.475 | 0.627 | 6.050 | 6.250 | 6.897 | 7.518 | 5.800 | 8.820 | 33 | 0.496 |

## Scomposizioni di esempio

### Sergio Camello (fixture 1038042, ruolo A)

- eleggibilità: `minutes_threshold` · minuti=24 · raw=5.900 · display=6.000 · provider=6.300
- ricostruzione: `6.0 + Σ = 5.900`

| componente | path | valore | coeff | contributo |
| --- | --- | ---: | ---: | ---: |
| shots_on | `shots.on` | 0.000 | 0.25 | 0.000 |
| shots_total | `shots.total` | 0.000 | 0.08 | 0.000 |
| key_passes | `passes.key` | 0.000 | 0.15 | 0.000 |
| dribbles_success | `dribbles.success` | 0.000 | 0.14 | 0.000 |
| duels_won | `duels.won` | 0.000 | 0.05 | 0.000 |
| fouls_committed | `fouls.committed` | 1.000 | -0.1 | -0.100 |

### Sergio Busquets (fixture 27410, ruolo C)

- eleggibilità: `minutes_threshold` · minuti=90 · raw=6.968 · display=7.000 · provider=7.300
- ricostruzione: `6.0 + Σ = 6.968`

| componente | path | valore | coeff | contributo |
| --- | --- | ---: | ---: | ---: |
| key_passes | `passes.key` | 1.000 | 0.18 | 0.180 |
| pass_accuracy | `passes.accuracy` | 0.920 | 0.9 | 0.828 |
| tackles | `tackles.total` | 2.000 | 0.08 | 0.160 |
| dribbles_success | `dribbles.success` | 0.000 | 0.12 | 0.000 |
| shots_on | `shots.on` | 0.000 | 0.15 | 0.000 |
| fouls_committed | `fouls.committed` | 2.000 | -0.1 | -0.200 |

### Benjamin Henrichs (fixture 1388490, ruolo D)

- eleggibilità: `minutes_threshold` · minuti=64 · raw=7.292 · display=7.500 · provider=6.500
- ricostruzione: `6.0 + Σ = 7.292`

| componente | path | valore | coeff | contributo |
| --- | --- | ---: | ---: | ---: |
| tackles | `tackles.total` | 2.000 | 0.12 | 0.240 |
| interceptions | `tackles.interceptions` | 2.000 | 0.1 | 0.200 |
| blocks | `tackles.blocks` | 0.000 | 0.1 | 0.000 |
| duels_won | `duels.won` | 3.000 | 0.06 | 0.180 |
| pass_accuracy | `passes.accuracy` | 0.840 | 0.8 | 0.672 |
| fouls_committed | `fouls.committed` | 0.000 | -0.1 | -0.000 |

### Marc-André ter Stegen (fixture 27410, ruolo P)

- eleggibilità: `minutes_threshold` · minuti=90 · raw=6.520 · display=6.500 · provider=6.500
- ricostruzione: `6.0 + Σ = 6.520`

| componente | path | valore | coeff | contributo |
| --- | --- | ---: | ---: | ---: |
| saves | `goals.saves` | 2.000 | 0.18 | 0.360 |
| pass_volume | `passes.total` | 20.000 | 0.008 | 0.160 |
| fouls_committed | `fouls.committed` | 0.000 | -0.12 | -0.000 |

## Note di calibrazione

Coefficienti `beta-v0.1` sono **sperimentali** (Master §8.1 / FR-SCO-01): servono a verificare coverage e spiegabilità offline, non a chiudere la formula definitiva.
