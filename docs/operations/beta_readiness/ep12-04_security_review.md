# EP12-04 — Security review

| Metadato | Valore |
| --- | --- |
| Card | EP12-04 |
| Epic | EP12 — Beta osservabile, sicura e recuperabile |
| Dipendenze | Tutte le Epic Must (M1–M4) — superficie applicativa da rivedere |
| Stima originale | 3–5 giorni |

## Stato implementazione (branch `claude/M5`)

**Eseguita interamente** (dependency audit, SAST, secret scan, review manuale OWASP,
test dinamico di bypass autorizzazione, job CI). **Aggiornamento EP12-03 (2026-08-21)**:
il load test ha riaperto la review sul rate limit login: `get_client_ip()` accettava
`X-Forwarded-For` da qualunque client e permetteva di cambiare arbitrariamente la chiave
del contatore. Il nuovo finding Medio #19 è stato corretto ignorando gli header inoltrati
nell'applicazione e affidandosi esclusivamente al peer già normalizzato dall'ASGI server
per proxy esplicitamente fidati; un test dinamico verifica il 429 anche variando XFF.
I risultati della chiusura precedente restano validi per gli altri finding.
**Aggiornamento sessione successiva**:
entrambi i finding Alti sono stati chiusi su decisione esplicita del responsabile della
card (vedi #5 e #6 sotto) — **nessun finding Alto resta aperto**. Il finding Medio
residuo (#7, header di sicurezza HTTP) è stato **accettato come rischio per la Beta**
su decisione esplicita del responsabile della card (stessa sessione di chiusura dei
finding Alti) — vedi dettaglio sotto. La breve riapertura sul finding #19 è ora chiusa.

### Riepilogo finding

| # | Finding | Severità | Stato |
| --- | --- | --- | --- |
| 1 | Segreto reale in `infra/local/.env.example:4` (`API_FOOTBALL_KEY`) | Alta | **Corretto** |
| 2 | PyJWT 2.10.1 vulnerabile (8 CVE) | Media | **Corretto** (→ 2.13.0) |
| 3 | python-multipart 0.0.20 vulnerabile (5 CVE, tocca upload avatar) | Media-Alta | **Corretto** (→ 0.0.32) |
| 4 | vite 6.3.5 / vitest 3.2.4 vulnerabili (incl. 1 critical, dev-only) | Alta (nominale) | **Corretto** (→ 6.4.3 / 3.2.7) |
| 5 | starlette 0.47.3 vulnerabile (DoS `Range` header su `FileResponse`/`StaticFiles`), bloccato dal pin `fastapi==0.116.1` | Alta (dipendenza) → **mitigata, vettore concreto chiuso** | **Mitigato** (guard applicativo, non bump fastapi) |
| 6 | CORS `allow_origins=["*"]` + `allow_credentials=True` | Media | **Corretto** (`allow_credentials=False`) |
| 7 | Nessun header di sicurezza HTTP (CSP/HSTS/X-Frame-Options/nosniff) | Media | **Rischio accettato per la Beta** |
| 8 | pip 25.0.1 vulnerabile nell'immagine backend (6 CVE, build-time only) | Bassa | Aperto, non corretto |
| 9 | pytest 8.4.1 vulnerabile (dev-only, DoS locale) | Bassa | Aperto, non corretto |
| 10 | Dipendenze transitive JS sotto `apps/mobile`/Expo (postcss, uuid, js-yaml, image-size, nanoid, brace-expansion) | Bassa (dev/build tool) | Aperto, non corretto |
| 11 | Playwright 1.49.1 → fix 1.55.1 (high, download browser senza verifica TLS) | Bassa | Aperto, non corretto |
| 12 | Bandit: 48 low (46 `assert_used`, 1 `try_except_pass`, 1 falso positivo `hardcoded_password_string`) | Bassa | Verificato, nessuna azione necessaria |
| 13 | Broken access control (authorization/router su tutti gli endpoint) | — | Verificato staticamente + dinamicamente, nessun finding |
| 14 | Injection (SQL) | — | Verificato, nessun finding |
| 15 | Rate limiting | — | Verificato, copertura più ampia del previsto, nessun finding |
| 16 | Upload avatar (tipo/dimensione/path traversal) | — | Verificato, nessun finding |
| 17 | Privacy/GDPR (`auth/privacy_service.py`) | — | Coperto da test esistenti, verificati verdi |
| 18 | Redazione log PII/segreti | — | Verificato agganciato globalmente, nessun finding |
| 19 | Trust incondizionato di `X-Forwarded-For` nel rate limit login | Media | **Corretto — peer ASGI trusted-only + test dinamico** |

### 1. Dependency audit — Python (`pip-audit`)

Nessun `pip-audit` nell'ambiente: installato nel container `api` già in esecuzione
(`docker compose exec api pip install pip-audit`), così da auditare l'esatto set di
dipendenze pinnate e installate in `backend/pyproject.toml` (Python 3.12, coerente con
`infra/local/Dockerfile`), non un venv locale scollegato (l'host ha Python 3.14, che
avrebbe richiesto reinstallare tutto e non avrebbe rispecchiato l'ambiente reale).

Comando: `docker compose exec api pip-audit`

**Prima dei fix**: 33 vulnerabilità note in 5 pacchetti (pip, pyjwt, pytest,
python-multipart, starlette). **Dopo i fix** (PyJWT + python-multipart bumpati, vedi
sotto): 15 vulnerabilità rimaste in 3 pacchetti (pip, pytest, starlette — tutti finding
aperti, vedi tabella).

- **PyJWT 2.10.1 → 2.13.0** (Media): 8 CVE, i più rilevanti riguardano
  `PyJWKClient`/allow-list di algoritmi multipli — **non applicabili al nostro uso**:
  `backend/src/auth/security.py` chiama `jwt.decode(token, secret,
  algorithms=["HS256"])` con whitelist esplicita a un solo algoritmo, mai `PyJWKClient`.
  Bump comunque applicato (costo zero, nessuna breaking change per l'API usata).
  Verificato: `tests/unit/auth/test_security.py` (roundtrip token) e l'intera suite
  `tests/integration/auth` (50 test) verdi dopo il bump.
- **python-multipart 0.0.20 → 0.0.32** (Media-Alta): 5 CVE — path traversal su
  `UPLOAD_DIR`/`UPLOAD_KEEP_FILENAME` (opzioni non usate dal nostro codice, FastAPI non
  le espone di default), DoS su parsing preambolo/epilogo multipart, `Content-Length`
  negativo non validato, nessun limite su numero/dimensione header di parte. Rilevante
  perché l'upload avatar (`POST /me/avatar`, `backend/src/auth/profile_router.py`) usa
  multipart/form-data reale. Verificato con
  `tests/integration/auth/test_profile.py::test_profile_avatar_upload_and_remove` (upload
  reale end-to-end) verde dopo il bump.
- **starlette 0.47.3** (**Alta, APERTO**): vedi sezione dedicata sotto.
- **pip 25.0.1** (Bassa, aperto): 6 CVE su path traversal nell'estrazione di
  wheel/tar durante `pip install`. Fix disponibile solo con bump major (25→26), fuori
  dallo scope "patch version compatibile" di questa sessione. Rischio pratico basso: pip
  è uno strumento di build (usato solo per installare le nostre dipendenze pinnate da
  PyPI durante `docker build`), non gira mai a runtime né elabora input da utenti finali.
- **pytest 8.4.1** (Bassa, aperto): 1 CVE (DoS locale via naming prevedibile di
  `/tmp/pytest-of-{user}`). Dev-only, mai in produzione. Fix richiede bump major (8→9)
  con rischio di rompere l'intera suite test — non "ovvio", lasciato aperto.

Verifica di non-regressione dopo i bump: rebuild immagine (`docker compose build api`),
`docker compose up -d --force-recreate api worker beat`, poi **intera suite pytest
backend** (`docker compose exec api python -m pytest`, `DATABASE_URL` puntato a
`postgres-test`): stesso identico set di 6 fallimenti pre-esistenti e non correlati (vedi
"Fallimenti pre-esistenti scoperti" più sotto), nessun fallimento nuovo introdotto dai
bump.

### 2. Dependency audit — JS/TS (`pnpm audit`)

Comando: `pnpm audit` (dalla radice del monorepo).

24 vulnerabilità: 1 critical, 15 high, 6 moderate, 2 low — **tutte in dipendenze di
build/dev tooling** (vite, vitest, playwright, postcss/uuid/js-yaml/image-size/
nanoid/brace-expansion annidati sotto `@expo/cli`), **nessuna nel bundle spedito agli
utenti finali**. Corrette solo le due pinnate direttamente e con bump patch/minor a
basso rischio:

- **vite 6.3.5 → 6.4.3** (`apps/web/package.json`): fix di high (arbitrary file read via
  WebSocket del dev server, `server.fs.deny` bypass su Windows) e moderate/low.
- **vitest 3.2.4 → 3.2.7** (`apps/web/package.json`, `packages/ui/package.json`): fix
  del **critical** (lettura/esecuzione file arbitraria quando il server UI di Vitest è in
  ascolto — mai esposto in CI/produzione, ma bump a costo zero).

**Non corretti** (aperti, bassa priorità): dipendenze transitive di `apps/mobile`
(postcss, uuid, js-yaml, image-size, nanoid, brace-expansion, annidate sotto
`expo`/`@expo/cli`/`@expo/metro-config`) — non pinnate direttamente da noi, un bump
richiederebbe `pnpm.overrides` o l'aggiornamento dell'intero SDK Expo, fuori scope "fix
ovvio". Playwright 1.49.1 → fix 1.55.1 (`apps/e2e/package.json`, high: download browser
senza verifica certificato SSL) non bumpato per non toccare la toolchain E2E appena
verificata verde due volte in EP12-01 senza ri-eseguire l'intera suite Playwright per
validare l'assenza di regressioni — lasciato aperto per decisione.

**Verifica limitata**: `pnpm install` è stato tentato **4 volte** dopo il bump e fallisce
sempre allo stesso punto — non nella risoluzione delle dipendenze (che riesce e produce
un `pnpm-lock.yaml` coerente e completo, diff verificato manualmente: solo
vite/vitest/`@vitest/*` passano da `3.2.4`/`6.3.5` a `3.2.7`/`6.4.3`, nessun altro
pacchetto tocca conflitti), ma nella fase di materializzazione di `node_modules`
(`ERR_PNPM_ENOENT: no such file or directory, scandir
.../node_modules/vite_tmp_<pid>/node_modules`), anche dopo aver ripulito la directory
temporanea residua. Non riproducibile in modo isolato nel tempo disponibile — sospetto
ambientale (Windows, possibile interferenza di antivirus/altro processo sulla stessa
working tree condivisa, coerente con la nota ambientale analoga già documentata da
EP12-01 per l'installazione di Playwright). **Il fix resta quindi verificato solo a
livello di risoluzione delle dipendenze (lockfile coerente), non con una run reale di
`pnpm test`/`pnpm build`** — da rieseguire in un ambiente pulito prima di considerarlo
definitivamente chiuso:
`pnpm install && pnpm --filter web test && pnpm --filter @fantappero/ui test && pnpm run build:web`.

### 3. SAST — `bandit` (backend Python)

Comando: `docker compose exec api bandit -r src -f json` (dopo
`docker compose exec api pip install bandit`).

**48 finding, tutti severità Bassa** (0 medium/high):

- **46× B101 `assert_used`** (CWE-703) — `assert` usati per invarianti interne dopo
  query DB (es. `src/market/trade_service.py:258,327,330,389,527`,
  `src/sports_data/provider/snapshots.py:83`, `src/sports_data/quality/retry.py:166`),
  non per validare input non fidato o confini di sicurezza. `python -O` (che li
  rimuoverebbe) non è usato in produzione qui (`uvicorn` avviato senza `-O`). Nessuna
  azione: rischio basso, non è un confine di sicurezza.
- **1× B110 `try_except_pass`** — `src/sports_data/fixtures/tasks.py:54` — intenzionale
  e commentato ("Never fail fixture sync because turn ensure enqueue failed"). Nessuna
  azione.
- **1× B105 `hardcoded_password_string`** — `src/database/enums.py:19` — **falso
  positivo**: è il valore `"password_reset"` di un enum (nome di un tipo di token, non
  una password). Nessuna azione.

### 4. Secret scanning

Due passaggi:

1. **`gitleaks`** (immagine `zricethezav/gitleaks:latest`, nessun binario disponibile
   nell'host, scaricata via `docker pull`) contro la storia git tracciata:
   `docker run --rm -v <repo>:/repo zricethezav/gitleaks:latest detect --source=/repo -v --report-format json --report-path /repo/gitleaks-history-report.json`
   (44 commit scansionati). **3 finding**: 1 reale (vedi #1 sotto), 2 falsi positivi in
   `backend/tests/unit/config/test_redaction.py:30,40` (valori fixture di test
   dichiaratamente finti, `abc123def456ghi789jkl012` e `tok_1234567890abcdef`, usati
   apposta per verificare che il redattore li mascheri).
   Una seconda run senza `--no-git` sull'intero working tree (inclusi `.pnpm-store`/
   `node_modules`, non tracciati) ha prodotto molto rumore aggiuntivo (stringhe ad alta
   entropia in bundle JS minificati di terze parti) — non significativo, escluso dalla
   valutazione finale usando la scansione sulla storia git tracciata sopra.
2. **Pattern manuale** mirato sul file `.env.example` a struttura ripetuta (grep +
   lettura diretta) — ha portato alla stessa scoperta di gitleaks in modo indipendente.

**1 finding reale, corretto**: `infra/local/.env.example:4` conteneva
`API_FOOTBALL_KEY=67d90279902aa6aa55cefd2263089ab9` — un valore nel formato esatto di
una chiave reale API-Football (32 caratteri esadecimali minuscoli), committato dal
commit `b343888` ("M1 + M3-1", 2026-08-05), documentato come **Secret: Sì** nella stessa
`docs/operations/configuration_and_secrets.md` del repo, in violazione diretta della
regola dichiarata lì ("Secrets never belong in the repository"). Il repo aveva già un
test dedicato (`backend/tests/unit/config/test_repo_secret_scan.py`) con un pattern che
avrebbe dovuto intercettarlo, ma il file `.env.example` è esplicitamente allowlistato
nel test stesso — quindi il segreto non veniva mai segnalato dalla suite esistente.
Nessun test/codice dipende dal valore letterale (verificato via grep sull'intero repo).
**Fix applicato**: sostituito con `fantappero_local_api_football_dev_only_replace_me`,
coerente con lo stile già usato nello stesso file per `JWT_SECRET_KEY` e
`BILLING_WEBHOOK_SECRET` (placeholder palesemente non funzionante, mai un valore che
sembri una credenziale reale). Non è stato necessario toccare il test allowlist (il
file resta legittimamente un `.env.example`, il problema era il *valore*, non la sua
presenza in un file esempio).

### 5. Review manuale OWASP Top 10

**Broken access control** — verificato **staticamente**: ogni router con endpoint
sensibili (`market/router.py`, `admin/router.py`, `billing/router.py`,
`ai_assistant/router.py`, `sports_data/quality/router.py`, `leagues/router.py`,
`fantasy_*`) usa `require_league_permissions(...)`/`require_permissions(...)` da
`backend/src/authorization/dependencies.py` — nessun endpoint sensibile trovato che si
affidi solo a un controllo lato UI. **Verificato anche dinamicamente** (test minimo
richiesto dalla card, non solo lettura statica): script Python ad hoc contro lo stack
Docker Compose reale (registrazione utente reale via `/auth/register`, verifica email
reale via Mailpit REST API, login reale), che tenta:
1. accesso senza token a un endpoint di lega → **401** (confermato)
2. accesso **da utente autenticato ma non membro** a una lega preesistente reale
   (`GET /leagues/{id}/mercato/asta/sessioni`) → **403 `league_access_denied`**
   (confermato — `authorization/service.py::resolve_league_access` applicato
   correttamente anche via chiamata HTTP diretta, non solo da UI)
3. stesso scenario in **scrittura** (`POST .../mercato/asta/sessioni`) → **403**
   (confermato)
4. utente normale contro un endpoint `Permission.GLOBAL_OPERATE`
   (`GET /sports-data/quality/summary`) → **403 `forbidden`** (confermato)
5. `GET /auth/me` → restituisce solo l'identità dell'utente autenticato (confermato)

8/8 controlli superati — nessun bypass riuscito. Verificato anche dal vivo con `curl`
che una richiesta OPTIONS con `Origin: https://evil.example.com` viene comunque
rifiutata sui path applicativi dalla stessa logica (non un bypass CORS dell'authz,
CORS e authz sono livelli indipendenti — vedi finding #6 per il problema CORS separato).

**Injection** — nessun uso di SQL raw non parametrizzato in `backend/src`: grep mirato
su costruzione dinamica di query (f-string, `.format()`, `%`) non ha trovato nulla; tutte
le occorrenze di `sqlalchemy.text(...)` sono default statici a livello di colonna/
constraint (`server_default=text("...")`, `postgresql_where=text("...")`), mai query con
input utente interpolato. Nessun finding.

**Autenticazione/sessioni** — `backend/src/auth/security.py`: hashing password con
Argon2 (`argon2-cffi`), JWT HS256 con whitelist esplicita di algoritmo, token opachi
(refresh) con hash SHA-256 lato server (mai il token in chiaro salvato). Rate limiting
reale su login/registrazione/reset (vedi punto rate limiting sotto). Nessun finding oltre
al bump PyJWT già applicato.

**Configurazione errata di sicurezza**:
- **CORS** (**Media, APERTO**) — vedi finding #6 dedicato sotto.
- **Header di sicurezza HTTP** (**Media, APERTO**) — vedi finding #7 dedicato sotto.
- `compose.yaml`: nessun segreto reale committato (tutte le password/secret nel file
  sono placeholder `_dev_only`/`_local_dev_only` espliciti, coerenti con
  `docs/operations/configuration_and_secrets.md`); nessun problema trovato.

**Upload non validati (avatar)** — `backend/src/auth/profile_service.py::upload_avatar`
+ `backend/src/auth/profile_validators.py::validate_avatar_upload`: tipo file verificato
via **magic bytes** (JPEG/PNG/WebP, non l'estensione/Content-Type dichiarato dal
client), dimensione limitata (`avatar_max_bytes`, default 2 MB via
`infra/local/.env.example`), nome file generato **server-side** da `user.id` (UUID) +
estensione derivata dal content-type rilevato — mai dal nome file inviato dal client,
quindi **nessun path traversal possibile**. Servito via `StaticFiles` su
`/media/avatars` (`backend/src/app/main.py:92`) — nota: questo endpoint statico eredita
la vulnerabilità DoS di starlette sul parsing del `Range` header, vedi finding #5.
Nessun finding aggiuntivo.

**Rate limiting** — verificato puntualmente (il piano segnalava incertezza, ipotizzando
un gap). Copertura reale via `AuthRateLimiter` (`backend/src/auth/rate_limit.py`,
contatori Redis a finestra fissa): login (5/min/IP, già noto da EP12-01), registrazione
(per ora), resend-verification (per ora), forgot-password (per ora) — tutti in
`backend/src/auth/service.py`. **Riuso confermato anche fuori da `/auth`**: directory
fantallenatori e creazione inviti nominativi
(`backend/src/leagues/named_invite_service.py::_check_rate_limit`). Gli endpoint
"costosi" citati esplicitamente dal piano sono protetti in modo diverso ma equivalente:
sync sportiva (`sports_data/quality/router.py`) richiede `Permission.GLOBAL_OPERATE`
(non pubblico → nessun bisogno di rate limit dedicato); gli endpoint AI assistente
(viceallenatore/osservatore/analista, `ai_assistant/router.py`) applicano una **quota
giornaliera per utente** (`_check_quota`/`billing.entitlement_service`) che funge da
rate limit funzionale. La copertura degli endpoint è confermata, ma l'assunzione sulla
provenienza dell'IP non lo è: `auth.dependencies.get_client_ip()` usa il primo valore di
`X-Forwarded-For` senza verificare che la richiesta provenga da un reverse proxy
fidato. Durante EP12-03 è bastato cambiare tale header per aggirare il limite
`5/min/IP`. **Finding #19 (Medio, corretto)**: `get_client_ip()` usa ora soltanto
`request.client`, che Uvicorn può riscrivere esclusivamente per i proxy configurati in
`FORWARDED_ALLOW_IPS`; l'app non interpreta più direttamente XFF. Il test dinamico
`test_login_rate_limit_ignores_client_supplied_forwarded_for` invia sei tentativi con
sei header diversi e verifica comunque il 429 finale. Il benchmark non sfrutta il bypass:
solo `api-perf` usa un limite esplicitamente alzato per il burst di setup, mentre lo stack
ordinario conserva il default 5/minuto.

**Privacy/GDPR** (`backend/src/auth/privacy_service.py`, `privacy_validators.py`) —
review leggera, appoggiata alla suite test esistente e dedicata
(`tests/integration/auth/test_privacy.py`, `test_privacy_idor.py`) verificata verde in
questa sessione (export, cancellazione con conferma password, IDOR su cancellazione
cross-utente). Nessun finding aggiuntivo identificato.

### Finding chiusi su decisione del responsabile (sessione successiva)

**#6 — CORS `allow_origins=["*"]` + `allow_credentials=True` (Media) — CORRETTO**

Decisione presa dal responsabile della card: dato che l'auth è Bearer-token-only (nessun
`Set-Cookie` in tutto `backend/src`, riconfermato con grep in questa sessione, e nessuna
chiamata `fetch` con `credentials: "include"` in `apps/web`/`apps/mobile`, anch'esso
riverificato), il fix più semplice che risolve il problema alla radice è portare
`allow_credentials` a `False` invece di introdurre un allowlist di origin per
ambiente (che avrebbe richiesto una nuova variabile di configurazione e sarebbe stata
comunque inutile senza credentials da proteggere). Applicato in
`backend/src/app/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # era True
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Verificato dal vivo dopo rebuild (`docker compose build api` +
`docker compose up -d --force-recreate api worker beat`):
```
curl -i -X OPTIONS http://localhost:8001/auth/me -H "Origin: https://evil.example.com" ...
→ prima: Access-Control-Allow-Origin: https://evil.example.com (riflesso) + Access-Control-Allow-Credentials: true
→ dopo:  Access-Control-Allow-Origin: * (letterale, non riflesso) + nessun header Access-Control-Allow-Credentials
```
Il vettore è chiuso: anche in presenza di credenziali browser-gestite in futuro, un sito
terzo non riceverebbe più una risposta CORS "valida" per richieste credenziali (la spec
CORS non permette `Access-Control-Allow-Origin: *` insieme a credentials, quindi il
browser scarterebbe la risposta).

**Verifica di non-regressione sull'app reale**: rieseguita l'intera suite Playwright
esistente (EP12-01, `apps/e2e`, 4 test — flusso positivo + 3 stati) contro lo stack
Docker Compose reale con l'API ricostruita: **verde** (`4 passed`, 44.7s) — login,
registrazione, creazione lega, formazione, mercato da UI reale continuano a funzionare
identicamente. Rieseguita anche l'intera suite `tests/integration/auth` +
`tests/unit/auth` (50 test, verdi) per escludere regressioni lato backend.

**#5 — starlette 0.47.3 vulnerabile (DoS `Range` header), bloccato dal pin
`fastapi==0.116.1` — MITIGATO (non bump fastapi)**

Prima di scegliere tra bump fastapi/accettazione rischio, verificato se il limite
dimensione avatar (`avatar_max_bytes`, 2 MiB, enforced server-side in
`profile_validators.py::validate_avatar_upload` prima ancora di scrivere il file)
riduce il blast radius, come suggerito. **Non lo riduce**: letta la PoC completa
dell'advisory (PYSEC-2026-1942) — il costo O(n²) è determinato dalla **lunghezza della
stringa dell'header `Range`** (regex `_parse_range_header` + merge loop sul numero di
range parsati), non dalla dimensione del file servito. La PoC ufficiale dimostra 3.2s di
CPU per un header di ~40 000 caratteri contro un file fittizio da 1 MB — un avatar da 2
MiB (o anche 100 byte) è ugualmente attaccabile con lo stesso header malevolo.
Dichiarare il rischio "Medio per via del limite upload" sarebbe stato scorretto; scelta
la strada della **mitigazione applicativa mirata** invece del bump fastapi (che
richiederebbe una regressione completa dell'intera superficie API, fuori scope per un
fix a basso rischio).

**Fix applicato**: nuovo middleware ASGI globale,
`backend/src/app/security_middleware.py::RangeHeaderGuardMiddleware`, registrato in
`backend/src/app/main.py` (`install_range_header_guard(app)`, prima del routing per
qualunque richiesta HTTP). Rifiuta con `400` qualunque richiesta il cui header `Range`
superi 512 byte, **prima** che raggiunga il codice vulnerabile di
`FileResponse`/`StaticFiles` — nessun caso d'uso legittimo (browser che richiede un
singolo range o pochi range per un'immagine/video) si avvicina a questa soglia (un
singolo range è ~20-30 caratteri), mentre la PoC dell'advisory richiede migliaia di
caratteri per produrre un costo CPU misurabile (0.05s a ~5 000 caratteri, 3.2s a ~40 000)
— a 512 byte il costo residuo è trascurabile (sub-millisecondo). Il guard è globale (non
solo su `/media/avatars`), quindi copre anche qualunque uso futuro di `FileResponse`
altrove nell'app.

Verificato dal vivo dopo rebuild:
```
# 1. Range legittimo corto su un path reale sotto /media/avatars → passa (404, file non esiste, non 400)
curl -i http://localhost:8001/media/avatars/nonexistent.jpg -H "Range: bytes=0-100"
→ HTTP/1.1 404 Not Found

# 2. Range malevolo (forma della PoC, ~5000 caratteri) sullo stesso path → bloccato PRIMA di StaticFiles
curl -i http://localhost:8001/media/avatars/nonexistent.jpg -H "Range: bytes=00000...0a-"
→ HTTP/1.1 400 Bad Request

# 3. Stesso header malevolo su una route completamente diversa (/health) → bloccato ugualmente (guard globale, non solo avatar)
curl -i http://localhost:8001/health -H "Range: bytes=00000...0a-"
→ HTTP/1.1 400 Bad Request

# 4. Header appena sotto la soglia (~410 byte) → passa normalmente (404, non 400)
curl -i http://localhost:8001/media/avatars/nonexistent.jpg -H "Range: bytes=000...0-1"
→ HTTP/1.1 404 Not Found
```

**Verifica di non-regressione sull'app reale**: rieseguita la suite Playwright completa
dopo l'aggiunta del guard globale (che intercetta *ogni* richiesta HTTP, non solo
`/media/avatars` — la verifica più rilevante qui, dato che tocca tutto il traffico
API↔web): **verde** (`4 passed`, 44.7s). Rieseguita anche `ruff check`/`ruff format
--check` su `main.py` e `security_middleware.py` (puliti). Nota collaterale osservata
durante la verifica: un primo run della suite E2E dopo il rebuild ha incontrato il rate
limiter reale di registrazione (`auth_rate_limit_register_per_hour`, pre-esistente,
non toccato in questa sessione) per via delle numerose registrazioni ripetute accumulate
nella stessa sessione (script di bypass authz + run E2E multipli ravvicinati) — non una
regressione: svuotate le chiavi Redis `auth:rl:register:*` (solo ambiente locale) e la
suite è tornata verde.

**Stato residuo**: la dipendenza `starlette` in sé **resta nominalmente vulnerabile**
secondo `pip-audit` (il pin `fastapi==0.116.1` blocca ancora l'aggiornamento diretto) —
questo non è un fix della CVE upstream, è una mitigazione applicativa che chiude il
vettore di attacco concreto per questa app. Il bump di fastapi resta un'azione valida
per il futuro (fuori scope qui per il rischio di regressione); se effettuato, il guard
di questa sessione può restare come difesa in profondità aggiuntiva senza conflitti.

### Rischi accettati (nessuna decisione ulteriore pendente)

**#7 — Nessun header di sicurezza HTTP (Media) — RISCHIO ACCETTATO PER LA BETA**

Decisione esplicita del responsabile della card: lasciare il gap documentato e non
implementare in questa milestone, per non introdurre un middleware CSP/HSTS non
validato senza le informazioni necessarie a farlo in sicurezza (vedi motivazione
sotto — un CSP sbagliato rompe l'intera app web). Da riprendere prima di un rollout
oltre la Beta pilota, quando saranno note le fonti reali script/style/font della SPA
e la terminazione TLS di produzione.

Verificato dal vivo (`curl -i http://localhost:8001/auth/me`): nessuna risposta include
`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`,
`Referrer-Policy` o `Strict-Transport-Security`. Non corretto in questa sessione perché
una policy corretta richiede decisioni prodotto/infra che non è "ovvio" prendere da
soli: CSP richiede conoscere tutte le fonti reali di script/stili/font usate dalla SPA
(un CSP sbagliato rompe l'intera app web, non è un fix "a basso rischio"); HSTS ha senso
solo dietro terminazione TLS reale (dipende da dove/come avviene in produzione, non
noto in questa sessione); `X-Frame-Options`/`X-Content-Type-Options` sarebbero
isolatamente più sicuri da aggiungere subito, ma è stato scelto di trattare l'intero
gruppo come un'unica decisione di policy invece di applicarne solo alcuni in modo
frammentario.

Opzioni per chi decide: definire la policy CSP reale (richiede audit delle fonti
script/style/font usate da `apps/web`), decidere se/dove terminare TLS per abilitare
HSTS in sicurezza, poi aggiungere un middleware FastAPI dedicato (`app.middleware("http")`
o `starlette.middleware` custom) che imposti questi header su ogni risposta.

### Fallimenti pre-esistenti scoperti durante la verifica (non causati da questa sessione)

Durante la run completa di `pytest` per verificare i bump di dipendenza, sono emersi 6
fallimenti **confermati pre-esistenti e non correlati** (riprodotti anche eseguendo gli
stessi test isolatamente, prima ancora di applicare i bump, o per esclusione diretta
della causa):
- `tests/unit/test_health.py::test_health_ok_without_deps`,
  `tests/unit/observability/test_health_probes.py::test_ready_ok_without_deps` —
  falliscono identicamente **con e senza** i bump di questa sessione (validation error
  pydantic su `DATABASE_URL` mancante) — problema del test/ambiente, non introdotto qui.
- `tests/test_sports_dataset.py::test_validate_sports_dataset_offline` — checksum del
  dataset fixture disallineati rispetto al manifest, causa esterna a questa sessione.
- `tests/integration/authorization/test_admin_panel.py::test_admin_listone_refresh_job_lifecycle_for_operator`,
  `tests/integration/notifications/test_market_event_notifications.py::test_trade_proposal_notifies_recipient`
  — errori di dominio (`assert 'queued' == 'failed'`,
  `ValidationAuthError: Devi richiedere almeno un calciatore o dei crediti.`) in
  `backend/src/market/trade_service.py`/pannello admin listone — **file al momento
  modificati da lavoro concorrente non di questa sessione** nel working tree condiviso
  (vedi `git status` finale), non toccati da EP12-04.
- `tests/unit/config/test_repo_secret_scan.py::test_no_secret_material_in_tracked_files`
  — fallisce **solo dentro il container `api`** per assenza del binario `git`
  (`FileNotFoundError: 'git'`, l'immagine `infra/local/Dockerfile` installa solo
  `curl`) — non riproducibile in un ambiente CI/dev normale con git disponibile;
  verificato indipendentemente che lo stesso identico controllo passa (nessun segreto
  residuo) eseguendo `gitleaks` fuori dal container, vedi sezione 4.

Nessuno di questi 6 è stato indagato oltre né corretto in questa sessione — fuori scope
per EP12-04 e, per i due di market/admin, potenzialmente in conflitto con lavoro
concorrente in corso sullo stesso file.

### Job CI aggiunti

In `.github/workflows/ci.yml`, tre nuovi job:

- **`python-sast`** (bandit, **bloccante**, in `needs` di `ci-success`) — analisi
  statica pura e deterministica del codice corrente, nessuna chiamata di rete il cui
  esito possa cambiare tra due run dello stesso commit: a differenza di
  `e2e-critical-flow` (informativo per flakiness reale di browser/Docker Compose), qui
  non c'è motivo di non bloccare. `bandit -r src -ll` fallisce solo su severità
  medium/high (oggi 0 — i 48 low sono accettati come da tabella sopra).
- **`secret-scan`** (gitleaks via `gitleaks/gitleaks-action@v2`, **bloccante**, in
  `needs` di `ci-success`) — stessa motivazione di determinismo di `python-sast`.
- **`dependency-audit`** (pip-audit + pnpm audit, **informativo**, `continue-on-error:
  true`, **non** in `needs` di `ci-success`) — a differenza dei due sopra, questi tool
  interrogano database di vulnerabilità esterni (PyPA advisory DB, GHSA) che cambiano
  **indipendentemente dal codice**: una CVE appena pubblicata su una dipendenza già
  pinnata e non toccata potrebbe far fallire il job tra due run dello stesso commit,
  bloccando merge non correlati al problema. Girato comunque su ogni push per visibilità
  immediata dei finding; da promuovere a bloccante in futuro solo quando esiste un
  processo di triage/waiver documentato (oggi non esiste).

Verificato solo che lo YAML è sintatticamente valido
(`python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`) e che i
comandi usati in ciascun nuovo step sono gli stessi già eseguiti ed evidenziati sopra in
questa sessione. **Non eseguito su un runner GitHub Actions reale** (nessun accesso in
questa sessione, stesso limite già segnalato da EP12-01).

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
