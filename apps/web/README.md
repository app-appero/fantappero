# apps/web

React (Vite) web app for FantApperò.

## Stack

React 19 + Vite 6, consumes `@fantappero/contracts` and `@fantappero/ui`, talks to `backend` over HTTP.

## Boundaries

- UI and client state only — no sports-provider keys or payment secrets.
- Game rules (lock, scoring, market) stay authoritative on the backend.
- Do not import Python modules from `backend`.

## Commands

```bash
pnpm --filter @fantappero/web dev
pnpm --filter @fantappero/web test
pnpm --filter @fantappero/web build
```

## Status

EPUI-01 — identità visiva documentata in `docs/design/`, token in `@fantappero/ui`, anteprima stati in `apps/web`.

EPUI-05 — shell responsive con route placeholder, `ThemeProvider`, `AppErrorBoundary`, skip link e verifica 360px–desktop. Vedi [`docs/design/shell.md`](../../docs/design/shell.md).
