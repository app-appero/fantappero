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

EP01-01 scaffold — minimal health page only.
