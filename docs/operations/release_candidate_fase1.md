# Release candidate Fase 1 — manifest (Blocco D1)

**Cos'è questo documento**: la "fotografia" precisa di quale versione esatta del codice, del database e delle app sarà sottoposta ai controlli obbligatori (D2), alle prove di carico (D3) e alla revisione di sicurezza (D4), prima del pilota. Senza questo, "abbiamo testato la release" non vuol dire niente — bisogna sapere esattamente *cosa* è stato testato.

**Stato: bozza aperta, non ancora congelata.** Contiene la fotografia di oggi, ma il vero "congelamento" (una versione precisa che non cambia più fino al pilota) avviene solo dopo che D2, D3 e D4 sono completati — altrimenti si rischia di validare una versione e poi spedirne un'altra al pilota. Vedi §4.

## 1. Manifest

```yaml
release: fase1-rc0                     # rc0 = bozza pre-D2/D3/D4, non ancora la candidata finale
commit: b327f1fa5744ca7fe1acfbc7d56d6dabc5476d00
branch: claude/fase1-chiusura
tag: (nessuno — non è mai stato creato un tag Git in questo repository)
freeze_date: 2026-09-27

database_revision: 37c365bf2399        # alembic heads, singola testa, nessun ramo aperto (72 migrazioni)

web_version: "0.0.0"                   # apps/web/package.json — versionamento non ancora impostato
mobile_version: "0.0.0"                # apps/mobile/app.json — idem, nessuna build iOS/Android numerata
contracts_version: "0.0.0"             # packages/contracts/package.json (condiviso web+mobile+backend)

docker_api_image: fantappero-backend:local
docker_api_image_id: sha256:8941335913ef670c49267402545230712decbf0ec5b68c9015a3eee4ab3502e6
# ^ digest locale, non di un registry: non è mai stata fatta una build "ufficiale"
# pubblicata da qualche parte — vedi §3.

pilot_environment: (da definire — Blocco E non ancora iniziato)

feature_flags:
  web:
    SHOW_WAIVER_TAB: false             # apps/web/src/pages/MarketHubPage.tsx
    SHOW_VOLUNTARY_RELEASE: false      # apps/web/src/pages/MarketPage.tsx
    SHOW_MARKET_HISTORY: false         # apps/web/src/pages/MarketPage.tsx
    SHOW_ROSTER_CSV_IMPORT: false      # apps/web/src/pages/RosterPage.tsx
  mobile:
    SHOW_WAIVER_TAB: false             # apps/mobile/src/navigation/marketHubTabs.ts
    SHOW_VOLUNTARY_RELEASE: false      # apps/mobile/src/screens/MarketScreen.tsx
    SHOW_MARKET_HISTORY: false         # apps/mobile/src/screens/MarketScreen.tsx
    SHOW_ROSTER_CSV_IMPORT: false      # apps/mobile/src/screens/RosterScreen.tsx
  # I 4 flag sono ora allineati identicamente su entrambe le piattaforme
  # (corretto il 26/09/2026, Blocco C1 — vedi registro_requisiti_fase1.md).
```

## 2. Perché "rc0" e non "rc1"

Il piano chiede di congelare una candidata *prima* di sottoporla ai controlli — ma qui i controlli (D2 bloccanti, D3 performance, D4 sicurezza) non sono ancora stati fatti sulla versione attuale. Chiamarla già "rc1" darebbe la falsa impressione di una versione già validata. **rc0** segna: "questa è la fotografia di partenza, la stessa identica versione su cui gireranno D2/D3/D4 — se quei controlli passano senza bisogno di altre modifiche, rc0 diventa semplicemente rc1 senza rifare la fotografia; se emergono correzioni, si aggiorna questo file con il nuovo commit e si passa a rc1 con le prove rifatte sulla versione corretta."

## 3. Scostamenti noti dal manifest "ideale" del piano

Il piano (Blocco D1) chiede anche un **digest di un'immagine Docker pubblicata** e **versioni/build numerate per iOS e Android**. Oggi non esistono:

- **Nessun registry Docker**: le immagini (`fantappero-backend:local`) sono costruite solo in locale, mai pubblicate. Il digest nel manifest sopra è quello dell'immagine locale — cambia a ogni build, non è un riferimento stabile. Per un pilota reale servirà una pipeline che costruisce e pubblica un'immagine con un tag fisso (es. su GitHub Container Registry), altrimenti "quale immagine gira in produzione" resta una domanda senza risposta verificabile.
- **Nessuna build mobile numerata**: `apps/mobile/app.json` ha `version: "0.0.0"` e non esistono build number iOS/Android distinti. Il mobile viene eseguito solo via Expo dev server o build locale (`expo run:android`, come fatto per il test E2E) — non esiste ancora un artefatto installabile distribuibile a un tester esterno.
- **Nessun tag Git**: mai usato in questo repository (`git tag -l` restituisce vuoto). Il commit SHA completo nel manifest è oggi l'unico riferimento affidabile.

Nessuno di questi tre punti blocca il lavoro di D2/D3/D4 in sé (si può testare comunque il commit attuale), ma **blocca la distribuzione reale ai tester del pilota** (Blocco G) — un tester non può installare "il commit `b327f1f`", ha bisogno di un file APK/IPA o di un link TestFlight/Play Console con un numero di build riconoscibile. Da affrontare prima di G, non necessariamente ora.

## 4. Evidenze — quali restano valide, quali vanno rifatte

| Evidenza | Data | Stato |
|---|---|---|
| Test E2E web (Playwright, `apps/e2e`) | in corso, CI `e2e-critical-flow` | **Aggiornato 27/09/2026 (D2)**: riparte da sola su ogni PR/push a main/dev (prima era agganciata a un branch `claude/M5` ormai inesistente, non partiva più). Resta informativa per i merge quotidiani (rischio di instabilità browser+Compose), ma il suo esito va controllato prima di dichiarare una candidata pronta per il pilota |
| Test E2E mobile (Maestro) | 27/09/2026 | **Nuova**, appena creata ed eseguita con successo in questo Blocco C2 — non esisteva prima di questa sessione |
| Performance/capacità (EP12-03) | 2026-08-21 | **Da rifare** (D3) — il piano stesso lo segnala esplicitamente: "le prove di agosto appartengono a una versione precedente", e da allora sono cambiati backend (fix B5, rotte turni) e mobile (persistenza sessione, ADR-0006) |
| Security review (EP12-04) | 2026-08-21, aggiornata su un punto | **Da rifare** (D4) — stessa ragione: oltre un mese di modifiche non riviste, incluso il nuovo storage sicuro della sessione mobile (`expo-secure-store`) che tocca proprio la superficie "gestione credenziali" tipicamente in scope di una security review |
| Matrice di parità web/mobile (C1) | 26/09/2026 | Valida, appena fatta |
| Registro requisiti completo | 26-27/09/2026 | Valido, aggiornato in continuo in questa sessione |

## 5. Prossimo passo

Procedere con **D2** (rendere bloccanti i gate oggi solo informativi) usando questo stesso commit come riferimento. Se D2 non richiede modifiche al codice, si passa a D3/D4 sullo stesso commit; se le richiede, questo manifest va aggiornato con il nuovo commit prima di rieseguire D3/D4 (altrimenti si rieseguono controlli su una versione già superata).
