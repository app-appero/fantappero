# Shell responsive web (EPUI-05)

Shell applicativa pronta per ospitare le feature M1–M4: layout, navigazione, route placeholder, gestione tema e confini di errore.

Dipendenze: [EPUI-02](./components.md), [EPUI-03](./navigation.md), [EPUI-04](./wireframes.md).

## Componenti shell

| Modulo | Ruolo |
| --- | --- |
| `AppLayout` / `AdminLayout` | Integrazione `@fantappero/ui` (`AppShell`, nav, header) |
| `ThemeProvider` | `data-theme`, `lang`, `data-surface` sul documento |
| `AppErrorBoundary` | Fallback UI per errori di render imprevisti |
| `SkipLink` | Salto al contenuto principale (`#main-content`) |
| `routeConfig.ts` | Registro dichiarativo delle route placeholder |
| `routes.tsx` | Mappatura path → pagine wireframe / placeholder |

## Superfici

| Superficie | `data-surface` | Layout |
| --- | --- | --- |
| App membro | `app` | Sidebar + bottom nav |
| Operatore globale | `admin` | Shell distinta (warning bar) |
| Autenticazione | `auth` | Senza shell (full-page form) |

## Route placeholder

Vedi [`navigation.md`](./navigation.md) per permessi e path. Gli stati UI (`?stato=loading|empty|error|success|forbidden`) sono wireframe EPUI-04 — nessun dato di produzione simulato.

**`/admin/*` non è più un placeholder wireframe (EP11-04a):** `AdminDashboardPage`, `AdminUsersPage`, `AdminLeaguesPage` sono pagine reali con dati dal backend, gated da sessione con `platform_role=operator`. `/dev/wireframes` e `/dev/design-system` restano wireframe placeholder, ma solo in `development` — 404 in produzione.

## Responsività

- Breakpoint nav: **768px** — sidebar desktop, bottom nav mobile
- Viewport minimo testato: **360px**
- `overflow-x: clip` sul body per evitare scroll orizzontale
- Padding ridotto su viewport stretti (`≤767px`)

## Accessibilità di base

- Landmark `main` con `id="main-content"`
- Skip link visibile al focus tastiera
- Nav con `aria-label` e `aria-current="page"` sulle voci attive
- Pannelli stato con `aria-live` / `role="alert"` dove applicabile

## Verifica locale

```powershell
pnpm install
pnpm test:packages
pnpm test:web
pnpm typecheck
pnpm build:web
```

Demo (solo `development`):

| Persona | URL |
| --- | --- |
| Membro | `/leghe` |
| Admin lega (wireframe lega) | `/leghe?persona=admin` |

Operatore (`/admin`): nessuna demo via query string — serve una sessione reale con `platform_role=operator` (bootstrap: [`docs/operations/admin_operator_bootstrap.md`](../operations/admin_operator_bootstrap.md)).

## Riferimenti

- [`visual-identity.md`](./visual-identity.md) — token e tema
- [`usage-guidelines.md`](./usage-guidelines.md) — stati UI
- Package UI: [`packages/ui/README.md`](../../packages/ui/README.md)
