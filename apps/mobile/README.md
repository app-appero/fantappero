# apps/mobile

App React Native (Expo) per FantApperò.

## Stack

Expo 54, React Navigation 7, tipi da `@fantappero/contracts`, token theme da `@fantappero/ui/theme`. Nessuna dipendenza runtime dal backend per lo sviluppo UI.

## Boundaries

- No API-Football keys or backend secrets on device.
- Same contract surface as web; no local scoring as source of truth.
- Do not access the database or workers directly.
- `@fantappero/ui`: solo token theme su mobile; componenti web restano web-only.
- Directory fantallenatori e inviti nominativi sono **demo-only**: dataset statici, resolver puri e
  stato React in memoria. Non effettuano networking, non persistono disponibilità/azioni e non
  rappresentano un contratto API o una fonte di verità.

## Shell (EPUI-06)

Navigazione strutturata con tab bar membro, stack admin/operatore e placeholder wireframe per ogni macro-area M1–M4.

| Comando | Descrizione |
| --- | --- |
| `pnpm --filter @fantappero/mobile start` | Dev server Expo (LAN) |
| `pnpm --filter @fantappero/mobile test` | Test unitari nav, wireframe, env |
| `pnpm --filter @fantappero/mobile typecheck` | Typecheck TypeScript |
| `pnpm --filter @fantappero/mobile build` | Verifica build (`tsc --noEmit`) |

## Demo sessione (dev)

1. Avvia l'app su emulator/device.
2. Tap **Demo** in header → cambia persona (Membro / Admin lega / Operatore).
3. Su schermate wireframe usa i chip **Stato UI** per loading/empty/error/success/forbidden.

## Directory e inviti nominativi (demo)

- **Crea lega**: dopo la validazione della fase 1 compare una fase 2 facoltativa con directory.
- **Admin lega**: la directory consente inviti nominativi simulati e mostra anche indisponibile,
  già invitato e capienza raggiunta.
- **Leghe → Inviti ricevuti**: elenco locale con accetta/rifiuta simulati.
- **Profilo**: toggle manuale per la disponibilità nella directory, valido solo per la sessione.
- Gli stati si possono forzare tramite parametri route demo (`stato`/`directory`): `loading`,
  `empty`, `error`, `success`, `forbidden`, `unavailable`, `already-invited`, `capacity`.

Documentazione shell: [`docs/design/shell-mobile.md`](../../docs/design/shell-mobile.md).

## Status

- EPUI-06 — shell mobile con navigazione, placeholder wireframe, sessione demo, error boundary.
- Feature M1+ e auth reale: EP02-03 e card di dominio successive.
