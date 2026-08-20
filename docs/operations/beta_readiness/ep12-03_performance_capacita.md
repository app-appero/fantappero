# EP12-03 — Performance e capacità

| Metadato | Valore |
| --- | --- |
| Card | EP12-03 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | Tutte le Epic Must (M1–M4); riusa scenario/dataset di EP12-01, presuppone invarianti EP12-02 verificate |
| Stima originale | 3–5 giorni |

## Obiettivo e scope

Misurare API, DB, worker, aggiornamenti live e picchi di carico; definire SLO Beta e
rispettarli sul carico concordato, con piano, dati di test, responsabile ed evidenze.

## Stato attuale nel repo (gap)

- **Nessun tool di load testing** presente (né k6, né locust, né altro) in `tools/`,
  `backend/`, o alla radice.
- **Nessuna metrica esportabile verso un backend esterno**: `backend/src/observability/metrics.py`
  implementa un `MetricsRegistry` in-process, esplicitamente commentato come
  "vendor-neutral; swap backend later" — non è un client Prometheus, non c'è
  `prometheus_client` né `opentelemetry-*` tra le dipendenze. Questo significa che oggi
  non esiste un modo standard di visualizzare le metriche sotto carico (Grafana/Prometheus
  non collegati).
- Nessuno SLO Beta è definito in nessun documento esistente (`docs/operations/` non ha un
  piano di capacity).
- `compose.yaml` definisce `worker` con `--concurrency=1`: valore adatto allo sviluppo
  locale ma da rivalutare esplicitamente come parametro di test di carico (potrebbe non
  riflettere la concorrenza di produzione).

## Piano d'azione

1. **Definire gli SLO Beta** (proposta di struttura, valori da concordare col team, non
   decidibili unilateralmente in fase di sola pianificazione):
   - Latenza API (p50/p95/p99) per gli endpoint critici del flusso EP12-01.
   - Throughput sostenibile (richieste/secondo) sul carico concordato (es. N leghe attive
     simultanee con M utenti ciascuna).
   - Tempo di elaborazione worker (Celery) per job critici (ricalcolo turno,
     sync sportiva).
   - Comportamento sotto "live update" (aggiornamenti in tempo reale durante una partita
     in corso, se già implementato — verificare in `backend/src/sports_data/scheduler/`).
   - Comportamento a picco (spike test): tempo di degrado/recupero.
2. **Scegliere ed integrare un tool di load testing** (vedi Tooling) con scenari basati
   sul flusso EP12-01 (login, consultazione lega, salvataggio formazione, azioni di
   mercato) più eventuali scenari di sola lettura ad alto volume (classifica, live score).
3. **Esporre metriche minime per l'osservazione del test di carico**: valutare se estendere
   `backend/src/observability/metrics.py` con un endpoint di scrape compatibile Prometheus
   (o, in alternativa più leggera per la Beta, loggare periodicamente uno snapshot del
   registry esistente durante il run di carico) — decisione da confermare in fase di
   implementazione, non in questa pianificazione.
4. **Eseguire i test di carico contro un ambiente Docker Compose dedicato** (stesso
   `compose.yaml`, eventualmente con override per risorse/concorrenza worker), non contro
   ambienti condivisi.
5. **Documentare risultati e SLO effettivi raggiunti** in un report allegabile alla card,
   con eventuali azioni correttive se gli SLO non sono rispettati.

## Tooling proposto

- **k6** (consigliato): script di carico in JavaScript, buon supporto Docker/CI, output
  strutturato (JSON/HTML) utilizzabile come evidenza. Alternativa: Locust (Python, più
  coerente con lo stack backend) — scegliere in base a preferenza del team in fase di
  implementazione, entrambi compatibili con l'approccio "solo Docker Compose, niente
  servizi installati localmente".
- Nessuna scelta definitiva presa in questa pianificazione: è una decisione tecnica da
  confermare all'avvio dell'implementazione.

## Dati di test

- Dataset e scenario "lega pronta" dallo script di seed E2E previsto in EP12-01, replicato
  N volte per simulare più leghe concorrenti.
- Fixture sportive esistenti (`backend/tests/fixtures/api_football/`) per evitare
  dipendenza dal rate limit del provider reale durante il carico.

## Criteri di accettazione (dalla card)

- SLO Beta definiti e rispettati sul carico concordato.
- Evidenze collegate alla card.

## Test minimi richiesti

- Smoke test dell'ambiente sotto carico e verifica di log, metriche, retry e
  configurazione (riusa probe `/live`/`/ready` già esistenti in
  `backend/src/observability/health.py`).
- Test di integrazione e regressione sui casi limite (picco improvviso, worker saturo,
  degrado e recupero).

## Rischi e domande aperte

- **Gli SLO Beta non sono ancora definiti da nessuna parte**: prima di poter dire "SLO
  rispettati" serve una decisione esplicita del team sui valori target (non deducibile
  dal codice). Questo documento propone la struttura, non i numeri.
- L'assenza di metriche esportabili è un gap reale: va deciso se per la Beta basta un
  report puntuale del test di carico o se serve investire in un backend di metriche
  osservabile in continuo (rimandabile a dopo la Beta se non bloccante).
- `worker: --concurrency=1` in `compose.yaml` è un vincolo dell'ambiente locale; il test
  di carico deve essere esplicito su quale concorrenza worker sta effettivamente
  misurando, per non produrre numeri fuorvianti.
