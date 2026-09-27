# Test E2E mobile (Maestro) — C2

**Stato: eseguito con successo il 27/09/2026 (Maestro CLI 2.10.0, emulatore Android
Pixel 6 / API 33).** Tutti i 13 passi passano, incluso il punto critico (sessione
ancora attiva dopo la chiusura completa dell'app). Vedi
`docs/operations/registro_requisiti_fase1.md`, sezione C2, per il log completo dei
problemi trovati e corretti durante il primo giro di prova dal vivo.

## Cosa copre

Il flusso `flows/full-season-smoke.yaml` esegue, in ordine, i 13 passi richiesti dal
criterio C2:

1. Registrazione nuovo utente
2. Verifica email (token recuperato da Mailpit, non da un vero indirizzo email)
3. Login
4. Creazione di una lega
5. Visualizzazione rosa
6. Apertura formazione (verifica solo che la schermata arrivi in uno stato noto —
   una lega appena creata ha rosa vuota, non esiste un modo a un tap per popolarla
   dal mobile; vedi nota sotto)
7. Visualizzazione turni europei
8. Visualizzazione mercato (tab "Scambi")
9. Logout
10. Login di nuovo
11. Chiusura completa dell'app (`stopApp`)
12. Riavvio dell'app (`launchApp`)
13. Verifica che la sessione sia ancora attiva dopo il riavvio (nessun redirect al login)

Il punto 13 è il vero obiettivo del test: prova che la sessione sopravvive alla
chiusura completa dell'app, non solo alla navigazione interna — cosa che prima di
C2 non era possibile perché la sessione viveva solo in memoria. **Verificato dal
vivo, non solo in teoria.**

## Prerequisiti

1. **Stack Docker** (dalla root del repo): `docker compose up -d --build postgres redis api mailpit worker`
   — **il `worker` è necessario**: l'invio email passa da una coda Celery che
   altrimenti nessuno svuota (scoperto durante il primo giro di prova). Se il
   worker principale è occupato con sync dati sportivi reali (può succedere, gira
   con `--concurrency=1`), l'email di verifica può restare in coda per minuti;
   in quel caso è utile un secondo worker temporaneo dedicato solo alla posta:
   ```bash
   docker run -d --name mailworker-tmp --network fantappero_default \
     --env-file infra/local/.env.example \
     -e DATABASE_URL="postgresql://fantappero:fantappero_local_dev_only@postgres:5432/fantappero" \
     -e REDIS_URL="redis://redis:6379/0" \
     -e CELERY_BROKER_URL="redis://redis:6379/0" \
     -e CELERY_RESULT_BACKEND="redis://redis:6379/1" \
     fantappero-backend:local \
     celery -A app.worker.celery_app worker --loglevel=INFO --concurrency=2 -Q celery
   # da rimuovere a fine sessione: docker rm -f mailworker-tmp
   ```
2. **Emulatore Android** con un AVD (l'SDK deve già essere installato):
   ```bash
   maestro start-device --platform android --device-os android-33
   ```
3. **App mobile installata sull'emulatore come dev client**, non Expo Go:
   `apps/mobile` usa moduli nativi (`expo-secure-store`, `expo-image-picker`).
   ```bash
   cd apps/mobile
   pnpm --filter @fantappero/contracts build
   pnpm --filter @fantappero/ui build
   pnpm --filter @fantappero/api-client build
   npx expo run:android
   ```
   La primissima build è lenta (compila codice nativo via NDK/CMake, scarica
   componenti SDK mancanti) — anche 10-15 minuti. Le build successive sono
   molto più rapide (cache Gradle).
4. **`apps/mobile/.env`** con `EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8001`
   e **`adb reverse`** per far vedere l'host come `localhost` dall'emulatore
   (più semplice di `10.0.2.2` con questo stack):
   ```bash
   adb reverse tcp:8001 tcp:8001
   adb reverse tcp:8025 tcp:8025
   ```
5. **Maestro CLI** installato (`curl -Ls "https://get.maestro.mobile.dev" | bash`).

## Come lanciarlo

```bash
cd apps/mobile/e2e/maestro
maestro test flows/full-season-smoke.yaml -e MAILPIT_BASE_URL=http://127.0.0.1:8025
```

Le altre variabili (email/nome/password di test, nome lega) sono generate
dentro il flow stesso con un timestamp, per poter rieseguire il test più volte
senza collisioni su email già registrate.

## Problemi trovati e corretti durante il primo giro di prova (27/09/2026)

Tutti nei file di test, non nell'app, tranne l'ultimo:

- Sintassi Maestro non valida: `timeout` va con `extendedWaitUntil`, non con
  `assertVisible`/`assertNotVisible`.
- La tastiera copriva campi/pulsanti sottostanti in tre form (registrazione,
  login, creazione lega) — serviva `hideKeyboard` prima di procedere.
- Il dominio email finto `@example.test` viene rifiutato dal backend come
  "riservato" — cambiato in `@example.com` (stesso dominio già usato dalla
  suite Playwright in `apps/e2e`).
- `http.get(...).body` in Maestro restituisce una stringa JSON grezza, non un
  oggetto già interpretato — lo script di recupero token va corretto con
  `JSON.parse`.
- Dopo la creazione, l'app porta a "Amministrazione lega", non "Home lega".
- I link Rosa/Formazione/Turni in Home lega esistono sempre nel codice ma sono
  sotto "Prossime fasi", fuori dallo schermo visibile — serve scorrere
  (`scrollUntilVisible`) prima di poterli toccare.
- La schermata Turni apre di default sulla tab "Calendario fantallenatori",
  non "Turni europei" — serve cambiare tab esplicitamente.
- **Bug reale nell'app** (non nel test): `GET /leagues/{id}/turni/da-aggiornare`
  rispondeva 422 per un problema di ordine delle rotte in
  `backend/src/fantasy_turns/router.py` (la rotta generica `{round_id}` era
  dichiarata prima di quella specifica "da-aggiornare", quindi FastAPI provava
  a interpretare "da-aggiornare" come un id). Corretto spostando la rotta
  specifica prima di quella generica — nessuna modifica alla logica del
  calendario/turni. Probabilmente colpiva anche il web (stesso backend).

## Limiti noti (non affrontati in questo giro)

- **Passo 6 (formazione)**: non prova il salvataggio vero — una lega appena
  creata ha rosa vuota e non esiste un modo a un tap per popolarla dal mobile.
  Per un test più completo servirebbe un seed diretto sul DB di test (come
  fanno i fixture pytest del backend), non azioni UI.
- Copre solo Android — nessun simulatore iOS disponibile su questa macchina
  (Windows). Accettato esplicitamente dal piano ("dispositivo/emulatore").
