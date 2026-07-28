# apps/mobile

React Native (Expo) app for FantApperò.

## Stack

Expo 53, types from `@fantappero/contracts`, tokens from `@fantappero/ui`, API via `backend`.

## Boundaries

- No API-Football keys or backend secrets on device.
- Same contract surface as web; no local scoring as source of truth.
- Do not access the database or workers directly.

## Commands

```bash
pnpm --filter @fantappero/mobile start
pnpm --filter @fantappero/mobile test
pnpm --filter @fantappero/mobile typecheck
```

## Status

EP01-01 scaffold — minimal health screen only.
