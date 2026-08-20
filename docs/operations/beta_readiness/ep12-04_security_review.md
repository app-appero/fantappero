# EP12-04 — Security review

| Metadato | Valore |
| --- | --- |
| Card | EP12-04 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | Tutte le Epic Must (M1–M4) — superficie applicativa da rivedere |
| Stima originale | 3–5 giorni |

## Obiettivo e scope

Verificare OWASP (Top 10), autorizzazioni, rate limit, upload e gestione segreti; nessuna
vulnerabilità critica/alta aperta al termine della review, con piano, dati di test,
responsabile ed evidenze.

## Stato attuale nel repo (gap)

- **Nessun tool di security scanning integrato in CI** (`.github/workflows/ci.yml` non ha
  job SAST, dependency audit o secret scanning).
- Punti di forza già presenti da verificare (non da ricostruire):
  - Autorizzazione centralizzata in `backend/src/authorization` (EP02-03) — verificare
    enforcement lato server su tutti gli endpoint sensibili, non solo lato UI.
  - Gestione segreti documentata in `docs/operations/configuration_and_secrets.md`
    (EP01-04) — verificare che sia effettivamente rispettata (nessun segreto in
    repository, `.env`, log).
  - Redazione PII/segreti nei log già implementata:
    `backend/src/observability/redact_logs.py`.
  - Modulo `backend/src/privacy` (EP02-04, eliminazione/esportazione account) —
    verificare che le regole GDPR-like siano coerenti con quanto la review richiede.
- Aree senza riscontro esplicito da verificare in review (non è chiaro dal codice se sono
  già coperte): rate limiting su endpoint pubblici/di autenticazione, validazione upload
  (avatar — vedi volume `avatar storage` in `compose.yaml`), header di sicurezza HTTP
  (CSP, HSTS, ecc.).

## Piano d'azione

1. **Dependency audit automatico**: eseguire e poi integrare in CI
   - `pip-audit` (o `safety`) sulle dipendenze Python (`backend/pyproject.toml`)
   - `pnpm audit` sulle dipendenze JS/TS (monorepo pnpm)
2. **SAST/lint di sicurezza**: eseguire `bandit` sul backend Python per pattern insicuri
   (uso di `eval`, comandi shell, deserializzazione non sicura, ecc.).
3. **Secret scanning**: verificare che nessun segreto sia presente nella history recente
   o nei file tracciati (es. `gitleaks` o strumento equivalente), in linea con la regola
   generale "non inserire segreti nel codice, nei log, nei test, nei commit".
4. **Review manuale mirata OWASP Top 10**, per ciascuna voce applicabile allo stack
   (FastAPI + React + Postgres):
   - Broken access control → verifica sistematica di `backend/src/authorization` contro
     endpoint sensibili (crediti, mercato, ruoli admin/operatore).
   - Injection → verifica che le query passino sempre per SQLAlchemy parametrizzato (no
     SQL raw non parametrizzato).
   - Autenticazione/gestione sessioni → review di `backend/src/auth`.
   - Configurazione errata di sicurezza → review `compose.yaml`, variabili d'ambiente,
     CORS, header HTTP.
   - Upload non validati → review del path di upload avatar (tipo file, dimensione,
     path traversal).
   - Rate limiting → verificare se esiste già (non risultato dalla ricognione iniziale)
     su login/registrazione e su endpoint costosi (es. sync sportiva, generazione
     formazione).
5. **Classificare i finding** per severità (critica/alta/media/bassa) e per ciascuno
   critico/alto: correggere prima della chiusura della card, oppure registrare
   un'accettazione formale del rischio (coerente con "Correggere o accettare
   formalmente ogni scostamento" richiesto dalla card).
6. **Aggiungere i controlli automatici (audit, SAST, secret scan) come job CI**, in modo
   che restino attivi anche dopo la Beta, non solo come esercizio una tantum.

## Tooling proposto

- `pip-audit` (o `safety`) — dependency audit Python.
- `pnpm audit` — dependency audit JS/TS (già disponibile via pnpm, nessuna nuova
  dipendenza da installare).
- `bandit` — SAST Python.
- `gitleaks` (o equivalente) — secret scanning.

## Dati di test

- Ambiente Docker Compose standard per verifiche dinamiche (es. tentativi di accesso non
  autorizzato via API reale, non solo lettura statica del codice).
- Nessun dato di produzione: tutte le verifiche vanno fatte contro dati di test/fixture.

## Criteri di accettazione (dalla card)

- Nessuna vulnerabilità critica/alta aperta.
- Evidenze collegate alla card.

## Test minimi richiesti

- Test del flusso UI con permessi insufficienti (già previsto trasversalmente dalla card
  EP12-01, riusabile qui come evidenza di enforcement).
- Smoke test di configurazione e segreti (nessun segreto esposto in log/risposte API).
- Test di integrazione sui casi limite di autorizzazione (bypass tentato via manipolazione
  diretta delle richieste API, non solo tramite UI).

## Rischi e domande aperte

- Il rate limiting non risulta dalla ricognizione iniziale del repo: va verificato
  puntualmente in fase di implementazione se esiste già a livello di reverse proxy/infra
  (fuori da `backend/src`) prima di assumere che manchi.
- La review manuale OWASP richiede giudizio umano su alcuni finding (es. accettazione
  rischio); questo documento definisce il processo, non sostituisce la decisione del
  responsabile della card.
