# apps/mobile

App React Native (Expo) per FantApperò.

## Stack

Expo 54, React Navigation 7, tipi da `@fantappero/contracts`, token theme da `@fantappero/ui/theme`.

## Boundaries

- No API-Football keys or backend secrets on device.
- Same contract surface as web; no local scoring as source of truth.
- Do not access the database or workers directly.
- `@fantappero/ui`: solo token theme su mobile; componenti web restano web-only.
- **Pannello globale operatore** (`/admin*` web): **web-only**. Su mobile resta uno shell placeholder raggiungibile solo in modalità demo operatore; non va portato come tool interno di produzione.

## M1 — allineamento funzionalità utente (M1-MOBILE-ALIGN)

Con sessione reale (login + `EXPO_PUBLIC_API_BASE_URL`) il mobile usa le **stesse API** del web:

| Area | Route stack / tab | Endpoint principali |
| --- | --- | --- |
| Lista leghe | tab `Leagues` | `GET/DELETE /leagues/mine`, `/leagues/{id}` |
| Home lega | `LeagueHome` | `GET /leagues/{id}`, `/partecipanti`, `/calendario` |
| Crea / Join | `CreateLeague`, `JoinLeague` | `POST /leagues`, `POST /leagues/inviti/accetta` |
| Admin lega | `LeagueAdmin` | amministrazione regolamento/membri/inviti/calendario/stato/delete |
| Inviti ricevuti | `ReceivedInvites` | `GET/POST /leagues/inviti-ricevuti…` |

Regole allineate al web: eliminazione solo `draft|configuring` + conferma esplicita; inviti codice/link con copia; placeholder M2 (rosa/formazione/turni) non navigabili.

Modalità **demo** (default senza token / DevSettings): fixture locali per walkthrough UX, come `?persona=` sul web.

Persistenza sessione: in-memory per processo app (token + `activeLeagueId`). Per persistenza cross-restart installare AsyncStorage in un follow-up.

Copia codice/link: sheet nativa `Share` (senza dipendenza clipboard extra).

## Comandi

| Comando | Descrizione |
| --- | --- |
| `pnpm --filter @fantappero/mobile start` | Dev server Expo (LAN) |
| `pnpm --filter @fantappero/mobile test` | Test unitari |
| `pnpm --filter @fantappero/mobile typecheck` | Typecheck TypeScript |
| `pnpm --filter @fantappero/mobile build` | Verifica build (`tsc --noEmit`) |

## Auth

All’avvio: schermata **Accedi** (come web `/accedi`). Nessuna modalità demo.
Logout → torna ad Accedi.

Per **device fisico** (Expo Go): in `apps/mobile/.env` usa l’IP LAN del PC
(`http://192.168.x.x:8001`), non `127.0.0.1`. Poi riavvia Expo.
Apri l’app scansionando il QR con Expo Go (stessa Wi‑Fi). Il tasto `a` richiede
emulatore/device Android con USB debugging.

Documentazione shell: [`docs/design/shell-mobile.md`](../../docs/design/shell-mobile.md).

## Status

- EPUI-06 — shell mobile con navigazione, placeholder wireframe, sessione demo.
- M1-MOBILE-ALIGN — leghe/home/join/create/admin/inviti allineati alle API web; M2 e admin globale restano fuori scope.
