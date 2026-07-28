# packages/ui

Design tokens and presentational primitives for `apps/web` and, where sensible, `apps/mobile`.

## Boundaries

- Presentation only — no league, scoring, or market rules.
- No secrets or provider API access.
- Must not import application code from `apps/*`.

## Commands

```bash
pnpm --filter @fantappero/ui build
pnpm --filter @fantappero/ui test
```

## Status

EP01-01 scaffold — token exports only.
