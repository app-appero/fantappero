# Test E2E mobile (Maestro) — bozza C2

**Stato: scritto, mai eseguito.** Questi file sono la prima bozza del flusso end-to-end
richiesto dal piano di chiusura Fase 1 (criterio C2). Prima di lanciarli va fatto un
giro di prova (dry run) sull'emulatore: alcuni selettori dinamici e un paio di note
lasciate nei commenti (`# NOTA:`) vanno confermati contro l'app reale, e la sintassi
YAML va validata contro la versione di Maestro CLI installata.

## Cosa copre

Il flusso `flows/full-season-smoke.yaml` esegue, in ordine, i 13 passi richiesti dal
criterio C2:

1. Registrazione nuovo utente
2. Verifica email (token recuperato da Mailpit, non da un vero indirizzo email)
3. Login
4. Creazione di una lega
5. Visualizzazione rosa
6. Salvataggio formazione
7. Visualizzazione turni/risultato
8. Visualizzazione mercato (tab "Scambi")
9. Logout
10. Login di nuovo
11. Chiusura completa dell'app (`stopApp`)
12. Riavvio dell'app (`launchApp`)
13. Verifica che la sessione sia ancora attiva dopo il riavvio (nessun redirect al login)

Il punto 13 è il vero obiettivo del test: prova che la sessione sopravvive alla
chiusura completa dell'app, non solo alla navigazione interna — cosa che prima di
C2 (vedi `docs/operations/registro_requisiti_fase1.md`, sezione C2) non era
possibile perché la sessione viveva solo in memoria.

## Prerequisiti

1. **Stack Docker minimo** (dalla root del repo): `docker compose up postgres redis api mailpit`
   — non serve `web`, solo backend + posta.
2. **Emulatore Android** con un AVD già creato (SDK già presente sulla macchina,
   ma nessun AVD configurato al momento della stesura — va creato la prima volta,
   es. con Android Studio o `avdmanager`).
3. **App mobile installata sull'emulatore come dev client**, non Expo Go:
   `apps/mobile` usa moduli nativi (`expo-secure-store`, `expo-image-picker`) che
   Expo Go supporta, ma per dare a Maestro un `appId` stabile da lanciare
   (`com.fantappero.mobile`, vedi `apps/mobile/app.json`) conviene comunque un
   dev client vero: `cd apps/mobile && pnpm expo run:android`.
4. **Server Expo** per `apps/mobile` con `EXPO_PUBLIC_API_BASE_URL` puntato su
   `http://10.0.2.2:8000` — `10.0.2.2` è l'host con cui l'emulatore Android vede
   la macchina che lo ospita, non `localhost`.
5. **Maestro CLI** installato (`curl -Ls "https://get.maestro.mobile.dev" | bash`).

## Come lanciarlo (quando si decide di eseguirlo)

```bash
cd apps/mobile/e2e/maestro
maestro test flows/full-season-smoke.yaml \
  -e MAILPIT_BASE_URL=http://10.0.2.2:8025
```

Le altre variabili (email/nome/password di test, nome lega) sono generate
dentro il flow stesso con un timestamp, per poter rieseguire il test più volte
senza collisioni su email già registrate.

## Cose da verificare al primo giro (non ancora provate)

- **Sintassi `runScript` e oggetto `http`**: lo script
  `scripts/fetchVerificationToken.js` assume l'API JS di Maestro per fare una
  richiesta HTTP e restituire un valore con `output.verificationToken` — va
  confermata contro la versione di Maestro installata, la sintassi è cambiata
  nel tempo tra le release.
- **Step 7 (risultato/turno)**: su una lega appena creata potrebbe non esserci
  ancora nessun turno con risultato reale (dipende dai dati sportivi già
  sincronizzati in ambiente di test). Lo step attuale si limita a verificare che
  la schermata Turni si apra e mostri l'elenco o lo stato vuoto — non assume un
  risultato specifico.
- **Step 6 (formazione)**: assume che al primo accesso la formazione proposta
  automaticamente sia già valida per il salvataggio diretto (`formation-save`).
  Se la lega richiede scelte manuali obbligatorie, questo passo va esteso.
- **Selettori con id dinamico** (es. `matchday-turn-{numero}`,
  `formation-starter-{indice}`): scritti con pattern regex (`id: ".*"`), da
  confermare che Maestro li interpreti come tali nella versione installata.

## Perché non è stato ancora eseguito

Due tentativi precedenti di farlo fare a un agente cloud sono stati interrotti
per motivi di costo/limiti di sessione, prima ancora che questi file esistessero.
Questa bozza è pensata per essere rivista a costo zero (solo lettura) prima di
decidere se e dove eseguirla davvero.
