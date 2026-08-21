# Performance e capacità Beta — runbook EP12-03

## Scopo e verdetto

Questo runbook esegue un benchmark ripetibile del flusso critico Beta su uno stack
Docker usa-e-getta. La baseline del 2026-08-21 passa tutti i gate tecnici proposti dopo
la remediation N+1 di rosa/formazione. I valori seguenti sono **budget Beta proposti**:
sono congelati nel codice e misurati, ma richiedono ratifica del team prima di diventare
SLO del pilot.

## Isolamento e guardrail

Il profilo Compose `performance` crea esclusivamente:

- `postgres-perf`, database `fantappero_performance` su `tmpfs`;
- `redis-perf`, senza snapshot o append-only file e su `tmpfs`;
- `api-perf` sulla porta host 8004, quattro worker Uvicorn di default;
- `worker-perf`, concorrenza Celery 2 di default;
- job one-shot `performance-seed` e `k6`.

Il seed e il benchmark Celery terminano con errore se host, nome database o conferma
`isolated-performance-only` non coincidono. Il wrapper rimuove solo una allowlist di
quattro servizi `*-perf`; non usa `docker compose down`, non monta volumi dati nominati
e non legge/scrive PostgreSQL o Redis dello stack dev/pilot. I dati scompaiono alla
rimozione dei container. Non modificare questi guardrail per puntare a un ambiente
condiviso.

Il solo `api-perf` usa `AUTH_RATE_LIMIT_LOGIN_PER_MINUTE=50`, necessario perché il setup
k6 autentica 20 account sintetici in un burst. Lo stack ordinario conserva il default
5/minuto. Lo script non invia `X-Forwarded-For`.

## Comandi operativi

Prerequisiti: Docker Compose, Git Bash su Windows o Bash su Linux/macOS, porte 8004 e
risorse sufficienti per quattro processi API. Nessuna installazione locale di k6 è
richiesta; l'immagine è fissata a `grafana/k6:0.54.0`.

```bash
make performance-smoke
make performance-test
```

Il primo comando esegue un VU per 15 secondi; il secondo ricrea lo stack, esegue smoke,
steady e spike/recovery. Variabili ammesse:

```bash
PERF_USER_COUNT=20 PERF_API_WORKERS=4 PERF_WORKER_CONCURRENCY=2 make performance-test
PERF_KEEP_STACK=1 make performance-smoke  # solo diagnosi manuale; poi rimuovere i servizi perf
```

Output runtime ignorato da Git: `artifacts/performance/results/`. I summary k6 contengono
solo aggregati sanitizzati, non token o payload del seed. In caso di errore viene salvato
anche `compose-failure.log`; verificare il log prima del rerun.

## Dataset e carico

Il seed riusa helper, catalogo, fixture e regole dello scenario E2E EP12-01. Crea 20
utenti, ciascuno con una lega attiva e una storica, rosa completa da 35 giocatori,
formazione 4-3-3 modificabile, risultato finale omologato, classifica e storico mercato.
Fixture locali evitano chiamate e quote del provider sportivo.

Ogni iterazione legge lega, rosa, formazione, risultati, classifica, anteprima svincolo e
storico mercato; il 20% salva idempotentemente la formazione e il 10% interroga `/ready`.
Il login avviene una volta per account nel setup di ogni scenario, quindi non rappresenta
un login storm durante lo spike.

- steady: salita a 20 VU in 15 s, 90 s costanti, discesa in 15 s;
- spike: salita a 20 VU in 10 s, salto a 60 VU per 15 s, recovery a 20 VU per 30 s,
  discesa in 10 s.

## Budget Beta proposti e congelati

Per smoke: errori HTTP <1%, check >99%, p95 globale <750 ms, throughput >1 req/s.

Per steady a 20 VU:

- errori <1%, check >99%, throughput >50 req/s, p95 globale <1.500 ms;
- login p95 <1.000 ms;
- lega, risultati, classifica, anteprima/storico mercato p95 <750 ms;
- rosa p95 <3.000 ms;
- lettura e salvataggio formazione p95 <2.000 ms.

Per spike a 60 VU: errori <2%, check >98%, throughput >40 req/s, p95 globale <5.000
ms; login <1.000 ms, endpoint leggeri <5.000 ms, rosa/formazione <8.000 ms. Nella
finestra recovery: errori <1% e p95 <1.500 ms.

Non allentare i gate dopo un fallimento. Archiviare il risultato, indagare la causa e
ripetere con identica configurazione. Qualunque cambio di topologia o dataset richiede
una nuova baseline chiaramente etichettata.

## Osservazione e lettura dei risultati

k6 è la fonte dei gate HTTP: summary, p95 per endpoint, error rate, check e throughput.
Il wrapper raccoglie inoltre `docker stats` per API/PostgreSQL/worker, `pg_stat_database`,
profondità coda Redis, ping Celery e tre benchmark task.

`/metrics` esporta in formato Prometheus contatori HTTP/errori, durata count/sum/max e
metriche job già registrate. Con più worker Uvicorn il registry è process-local e lo
scrape può colpire un processo diverso: lo snapshot prova l'esportabilità ed è utile per
diagnosi per-processo, ma **non** è un conteggio aggregato del run. Per un pilot con
scrape continuo serve un backend multiprocess o un collector esterno; limitare inoltre
l'accesso a `/metrics` al piano operativo/reverse proxy.

Celery viene verificato separatamente perché il percorso HTTP non genera in modo
rappresentativo job pesanti. Il batch da 100 ping misura broker/queue/result backend; i
20 `fantasy_turns.ensure_upcoming` invocano il task di dominio reale. Con il dataset
attuale quest'ultimo può restituire zero elementi elaborati, quindi non è un benchmark di
ricalcolo massivo. `sports_data.poll_live_window` viene invocato una volta ma restituisce
`skipped_disabled`: il provider rimane intenzionalmente disabilitato e non esiste un
canale SSE/WebSocket da caricare. Non dichiarare copertura live su questa evidenza.

## Diagnosi e remediation

Se rosa o formazione degradano, eseguire prima il test di query-budget
`test_full_roster_and_lineup_query_counts_are_bounded`: su una rosa da 35 giocatori deve
restare entro 25 query per `/rosa` e 35 per `/formazione`. Un aumento segnala la
reintroduzione di query per atleta/ruolo/club.

Se API CPU resta prossima alla capacità disponibile, ridurre il carico non costituisce
una remediation. Profilare i path più lenti, rimuovere N+1 e poi valutare più CPU/worker
con una nuova baseline. Se PostgreSQL mostra deadlock, file temporanei o rollback non
spiegati, conservare gli artefatti e fermare il gate. Coda Redis diversa da zero dopo il
run richiede ispezione del worker prima di un nuovo test.

Il finding `X-Forwarded-For` emerso durante la diagnosi è registrato e corretto in EP12-04:
l'app usa il peer normalizzato dal server ASGI e non interpreta direttamente header
sintetici. Un deploy dietro reverse proxy deve configurare `FORWARDED_ALLOW_IPS` con la
sola allowlist dei proxy effettivamente fidati.

## Evidenze

- [Report sintetico 2026-08-21](./evidence/ep12-03_capacity_2026-08-21.md)
- [Card e stato implementazione](./beta_readiness/ep12-03_performance_capacita.md)

Gli artefatti completi locali sono diagnostici e non vanno committati: possono contenere
log voluminosi o identificativi sintetici e sono già coperti da `.gitignore`.

Il job CI informativo `performance-smoke` esegue lo stesso stack con un solo utente su
run manuali e sul branch M5; il full steady/spike resta un gate operatore, perché la
capacità del runner GitHub non è la capacità del pilot.
