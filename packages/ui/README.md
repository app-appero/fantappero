# packages/ui

Design tokens and presentational primitives for `apps/web` (incluso futuro pannello admin) and `apps/mobile`.

## Boundaries

- Presentation only — no league, scoring, or market rules.
- No secrets or provider API access.
- Must not import application code from `apps/*`.
- Component copy (labels, titles, messages) is passed via props from apps — not hardcoded in the package.

## Usage

### TypeScript tokens and components

```typescript
import {
  theme,
  Button,
  Input,
  Card,
  Tabs,
  EmptyState,
  UiStatePanel,
} from "@fantappero/ui";
```

### CSS (web / admin)

```css
@import "@fantappero/ui/theme.css";
```

Documentazione:

- [`docs/design/visual-identity.md`](../../docs/design/visual-identity.md) — EPUI-01
- [`docs/design/components.md`](../../docs/design/components.md) — EPUI-02 componenti
- [`docs/design/usage-guidelines.md`](../../docs/design/usage-guidelines.md)

## Commands

```bash
pnpm --filter @fantappero/ui build
pnpm --filter @fantappero/ui test
pnpm --filter @fantappero/ui typecheck
```

## Status

- **EPUI-01** — identità visiva, token semantici, CSS variables, validazione WCAG AA, `UiStatePanel`
- **EPUI-02** — breakpoint/z-index, componenti fondamentali (Button, Input, Select, Card, Badge, Tabs, Modal, Toast, Table, Skeleton, EmptyState), stati e documentazione d'uso
