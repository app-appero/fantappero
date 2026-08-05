# Navigazione e layout (EPUI-03)

Architettura shell per web (router leggero in `apps/web/src/router/simpleRouter.tsx`) e mobile (tab bar RN). Copy utente nelle app; componenti strutturali in `@fantappero/ui`.

## Superfici

| Superficie | Attributo | Ruolo | Esempio route |
| --- | --- | --- | --- |
| App lega | `data-surface="app"` | Partecipante / admin lega | `/turni`, `/rosa` |
| Operatore globale | `data-surface="admin"` | Staff piattaforma | `/admin`, `/admin/leghe` |

Il pannello admin usa trattamento visivo distinto (bordo warning, header dedicato) e route separate sotto `/admin/*`.

## Web — componenti layout (`@fantappero/ui`)

| Componente | Uso |
| --- | --- |
| `AppShell` | Contenitore root con header, sidebar, main, bottom nav |
| `AppHeader` | Brand, selettore lega, azioni utente |
| `SidebarNav` | Navigazione desktop (≥768px) |
| `BottomNav` | Navigazione mobile (<768px) |
| `PageContainer` | Titolo, breadcrumb slot, corpo pagina |
| `Breadcrumb` | Percorso gerarchico |
| `LeagueSelector` | Select lega attiva |

## Web — componenti dominio (presentazionali)

| Componente | Uso |
| --- | --- |
| `KpiCard` | Metriche turno / lega |
| `PlayerCard`, `PlayerRow` | Giocatore (card o riga tabella) |
| `MatchCard` | Partita programmata / live |
| `FormationView` | Modulo e slot formazione |
| `ResultCard` | Risultato fantasy (anche provvisorio) |
| `AnomalyIndicator` | Segnalazione anomalie dati |
| `StandingsTable` | Classifica lega (EPUI-04) |
| `AuctionBidPanel` | Offerta asta buste chiuse (EPUI-04) |
| `AuthFormLayout` | Shell form login/registrazione (EPUI-04) |
| `WireframeSection` | Regione annotata wireframe (EPUI-04) |

Tutte le label di stato (`statusLabel`, `severityLabel`, …) arrivano dalle app.

## Permessi

Tipi e regole in `@fantappero/contracts` (`auth.ts`):

- Ruoli globali: `member`, `global_operator`
- Ruoli lega: `member`, `league_admin`
- Permessi granulari (`market:manage`, `global:operate`, …)

Filtraggio voci menu: `hasPermissions` + catalogo in `apps/web/src/navigation/navConfig.ts`.

**EP02-03:** policy applicate lato server (`backend/src/authorization/`). I client continuano a usare `@fantappero/contracts` per il filtraggio UX; la web app può collegare `GET /leagues/mine` al posto delle leghe demo quando non in modalità persona.

## Route web (MVP layout + wireframe EPUI-04)

| Path | Permesso minimo |
| --- | --- |
| `/accedi` | — (layout senza shell) |
| `/leghe` | `league:view` |
| `/turni` | `matchday:view` |
| `/classifica` | `matchday:view` |
| `/rosa` | `roster:view` |
| `/formazione` | `roster:view` |
| `/asta` | `market:view` |
| `/mercato` | `market:view` |
| `/lega/amministrazione` | `league:admin` |
| `/profilo` | `profile:view` |
| `/dev/wireframes` | — (dev) |
| `/admin` | `global:operate` + ruolo globale |

Stati wireframe: `?stato=loading|empty|error|success|forbidden` — vedi [`wireframes.md`](./wireframes.md).

## Mobile

Tab bar in `apps/mobile/src/navigation/AppTabNavigator.tsx` con catalogo `MOBILE_NAV_ITEMS`, stack admin separato e stesso modello permessi della web. Vedi [`shell-mobile.md`](./shell-mobile.md).

## Verifica locale

```powershell
pnpm install
pnpm test:packages
pnpm test:web
pnpm test:mobile
pnpm typecheck
pnpm build:web
```

Demo permessi web:

- Membro: `/leghe`
- Admin lega: `/leghe?persona=admin` → voce «Admin lega»
- Operatore: `/admin?persona=operator`

## Riferimenti

- [`components.md`](./components.md) — primitive EPUI-02
- [`shell.md`](./shell.md) — shell responsive EPUI-05
- [`usage-guidelines.md`](./usage-guidelines.md) — density e stati
- [`visual-identity.md`](./visual-identity.md) — breakpoint e `data-surface`
- [`wireframes.md`](./wireframes.md) — wireframe EPUI-04
