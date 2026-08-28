# Navigazione e layout (EPUI-03)

Architettura shell per web (router leggero in `apps/web/src/router/simpleRouter.tsx`) e mobile (drawer RN). Copy utente nelle app; componenti strutturali in `@fantappero/ui`.

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

## Gruppo «Lega» (EP13-P01)

Le tre destinazioni di lega sono correlate ma non equivalenti: **Le mie leghe** (`/leghe`) sceglie il contesto globale, **Home lega** (`/lega/home`) mostra la lega attiva, **Amministrazione lega** (`/lega/amministrazione`) la modifica. Sono raccolte in un gruppo espandibile «Lega», definito in `APP_NAV_GROUPS` (web) e `MOBILE_NAV_GROUPS` (mobile) — stessi `itemIds`, stesse etichette.

Regole:

- **Turni** resta destinazione primaria indipendente: è il flusso più usato e non va nascosto in un sottomenu.
- **Inviti ricevuti** resta fuori dal gruppo perché è account-level e può riguardare più leghe.
- La visibilità del gruppo è **derivata**: un gruppo senza voci autorizzate non viene reso. «Amministrazione lega» compare solo con `league:admin`; per gli altri utenti la voce è assente e la route risponde comunque `forbidden` lato guard (vedi sotto).
- Il gruppo è aperto per default; lo stato chiuso è conservato per la sessione (web: `sessionStorage` chiave `fa.nav.groups.collapsed`; mobile: stato del drawer).
- Il toggle è un `<button>` con `aria-expanded`/`aria-controls` sul web e `accessibilityState={{ expanded }}` su mobile; il gruppo si evidenzia quando contiene la voce attiva.
- Nessun path, deep link o permesso è stato modificato dal raggruppamento.

**Bottom nav web (<768px):** resta piatta — una barra non annida sottomenu. Usa le etichette compatte di `NAV_SHORT_LABELS` («Leghe», «Admin lega»); sidebar e drawer usano quelle estese.

**Deep link amministrativo:** sul web `/lega/amministrazione` è protetto da `RequirePermissions required={["league:admin"]}` (`apps/web/src/routes.tsx`) che rende `UiStatePanel state="forbidden"`. Su mobile la protezione equivalente è dentro `LeagueAdminScreen` (`can(["league:admin"])` → pannello forbidden). L'app mobile **non ha oggi una configurazione `linking`/URL scheme**: non esistono deep link URL, quindi la superficie verificabile è la navigazione programmatica alla route `LeagueAdmin`. Introdurre uno schema di deep link è una decisione fuori dallo scope di EP13-P01.

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
| `/dev/wireframes` | — (solo `development`; 404 in produzione, EP11-04a) |
| `/admin` | `global:operate` + ruolo globale (sessione reale, non `?persona=`) |

Stati wireframe: `?stato=loading|empty|error|success|forbidden` — vedi [`wireframes.md`](./wireframes.md).

## Mobile

Navigazione **solo drawer**: `apps/mobile/src/navigation/AppTabNavigator.tsx` monta un `Tab.Navigator` con `tabBar={() => null}`, usato come router interno; la bottom tab bar non è visibile. Il menu è `AppDrawer` con catalogo `MOBILE_DRAWER_NAV_ITEMS` e gruppo `MOBILE_NAV_GROUPS`, stack admin separato e stesso modello permessi del web. Vedi [`shell-mobile.md`](./shell-mobile.md).

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
- Admin lega (solo `development`, wireframe lega): `/leghe?persona=admin` → voce «Admin lega»

**Pannello operatore (`/admin`, EP11-04a):** `?persona=operator` è stato dismesso — non autentica più e non apre `/admin` in nessun ambiente. L'accesso richiede una sessione reale con `platform_role=operator`; vedi [`docs/operations/admin_operator_bootstrap.md`](../operations/admin_operator_bootstrap.md) per creare/promuovere un operatore. `?persona=admin` resta debito tecnico limitato ai wireframe lega in `development` e non deve mai dare accesso al pannello operatore.

## Riferimenti

- [`components.md`](./components.md) — primitive EPUI-02
- [`shell.md`](./shell.md) — shell responsive EPUI-05
- [`usage-guidelines.md`](./usage-guidelines.md) — density e stati
- [`visual-identity.md`](./visual-identity.md) — breakpoint e `data-surface`
- [`wireframes.md`](./wireframes.md) — wireframe EPUI-04
