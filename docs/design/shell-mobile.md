# Shell mobile React Native (EPUI-06)

Shell nativa Expo pronta per ospitare le feature M1–M4: navigazione strutturata, placeholder wireframe, sessione demo, tema condiviso e error boundary.

Dipendenze: [EPUI-01](./visual-identity.md), [EPUI-03](./navigation.md), [EPUI-04](./wireframes.md), [EPUI-05](./shell.md) (web come riferimento).

## Stack navigazione

| Libreria | Ruolo |
| --- | --- |
| `@react-navigation/native` | Container (nessuna configurazione `linking`: non esistono deep link URL) |
| `@react-navigation/bottom-tabs` | Router interno delle schermate membro (tab bar non renderizzata) |
| `@react-navigation/native-stack` | Stack root, admin, schermate fuori tab |
| `react-native-safe-area-context` | Safe area header e drawer |
| `react-native-screens` | Performance native stack |

## Superfici

| Superficie | Dove | Trattamento visivo |
| --- | --- | --- |
| App membro | `AppTabNavigator` | Header app + drawer laterale |
| Admin lega | Stack `LeagueAdmin` | Header stack, voce nel gruppo «Lega» del drawer |
| Operatore globale | `AdminNavigator` | Header `surface="admin"` (bordo warning) |
| Autenticazione | Stack `Auth` | Full-page, senza drawer |

## Menu membro (drawer)

La navigazione è **solo drawer**: `AppTabNavigator` monta `Tab.Navigator` con `tabBar={() => null}` e lo usa come router interno; la bottom tab bar non è visibile. Voci allineate alla web (`APP_NAV_ITEMS` ↔ `MOBILE_DRAWER_NAV_ITEMS`), filtrate con `hasPermissions`:

- **Gruppo «Lega»** (espandibile, `MOBILE_NAV_GROUPS`): Le mie leghe · Home lega · Amministrazione lega
- **Destinazioni indipendenti:** Turni · Fantallenatori · Inviti · Classifica · Rosa · Formazione · Asta · Svincolati · Mercato · Profilo

Il gruppo è aperto per default, conserva lo stato aperto/chiuso per la sessione ed espone `accessibilityState={{ expanded }}`; la voce corrispondente alla schermata corrente è evidenziata. «Amministrazione lega» compare solo con `league:admin` e `LeagueAdminScreen` verifica comunque il permesso, mostrando il pannello `forbidden` a chi vi arriva per via programmatica.

**Fuori dal drawer:** Pannello operatore (stack admin, voce dedicata in fondo al drawer per `global:operate`).

## Placeholder wireframe

Copy condiviso in `@fantappero/contracts` (`wireframes.ts`), derivato dal catalogo EPUI-04.

Stati UI selezionabili in dev tramite chip «Stato UI» su ogni schermata wireframe (`navigation.setParams({ stato })`), analogo a `?stato=` sulla web.

## Sessione demo

Fino a EP02-03: `DemoSessionProvider` con persona `member` | `admin` | `operator`.

- **Dev:** pulsante «Demo» in header → schermata persona
- Admin lega: attiva lega con ruolo `league_admin`
- Operatore: mostra link «Pannello» e stack admin distinto

## Moduli principali

| Percorso | Ruolo |
| --- | --- |
| `apps/mobile/src/navigation/` | Navigator, catalogo tab, tipi route |
| `apps/mobile/src/layout/` | `AppHeader`, `PageContainer` |
| `apps/mobile/src/wireframes/` | Placeholder e stato UI |
| `apps/mobile/src/session/` | Sessione demo e permessi |
| `apps/mobile/src/errors/AppErrorBoundary.tsx` | Fallback errori render |
| `apps/mobile/src/components/UiStatePanel.tsx` | Pannelli stato RN (token theme) |

## Verifica locale

```powershell
pnpm install
pnpm test:mobile
pnpm typecheck
pnpm --filter @fantappero/mobile build
pnpm --filter @fantappero/mobile start
```

Demo permessi su device/emulator:

1. Apri app → icona menu in header → drawer con gruppo «Lega» e destinazioni indipendenti
2. Header «Demo» → persona Admin lega → nel gruppo «Lega» compare «Amministrazione lega»
3. Persona Operatore → voce «Pannello globale» → shell admin con bordo warning
4. Su Leghe/Turni/Rosa → chip stati loading/empty/error/forbidden

## Fuori scope (M1 / EP02-03)

- Login reale e API auth
- Dati lega/roster/mercato da backend
- Primitive `@fantappero/ui` DOM su RN (solo token theme)
- Hub `/dev/wireframes` web replicato integralmente

## Riferimenti

- [`navigation.md`](./navigation.md)
- [`shell.md`](./shell.md)
- [`wireframes.md`](./wireframes.md)
- Package: [`apps/mobile/README.md`](../../apps/mobile/README.md)
