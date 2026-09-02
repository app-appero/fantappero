# Linee guida d'uso UI (EPUI-01, EPUI-02)

Regole per web app, pannello admin e mobile. Obiettivo: coerenza visiva e accessibilità senza valori hardcoded nelle schermate.

Documentazione componenti: [`components.md`](./components.md).

## Usi corretti

### Colori e contrasto

- Testo corpo: `foreground` su `background` o `backgroundElevated`
- Testo secondario: `foregroundMuted` (validato WCAG AA su sfondo scuro)
- Link e CTA primarie: `accent` — per testo piccolo preferire peso ≥ 500 o dimensione ≥ 18px
- Stati: `success`, `warning`, `danger` solo per feedback esito, mai come decorazione
- Focus tastiera: anello `focusRing` / `--fa-shadow-focus`

### Gerarchia

1. **Display / title** — contesto (lega, turno, mercato)
2. **Heading** — sezioni e card
3. **Body** — copy e descrizioni
4. **Label / caption** — metadati, timestamp
5. **Stat** — numeri fantasy (mono, allineamento tabulare)

### Densità (interfacce fantasy)

| Contesto | Preset | Esempio |
| --- | --- | --- |
| Rose, mercato, classifica | `density.compact` | Più righe visibili, gap 8px |
| Navigazione lega, form | `density.comfortable` | Default app e admin |
| Onboarding, stati vuoto | `density.spacious` | Padding 40px, respiro |

Admin (`data-surface="admin"`): stessi token, gap leggermente ridotto via CSS.

### Stati interfaccia

Usare `UiStatePanel` per stati **pagina** (loading, empty, error, success, forbidden).

Per liste o sezioni vuote inline preferire `EmptyState`; per caricamento listati usare `Skeleton`.

### Componenti form e layout

- Azioni: `Button` (`primary` / `secondary` / `ghost` / `danger`)
- Campi: `Input`, `Select` — sempre label via props
- Contenitori: `Card`, `Badge`, `Table`, `Tabs`, `Modal`, `Toast`
- Brand: `BrandLogo` (`mark` / `full`) + sfondo decorativo `.fa-surface-pitch` su auth e shell app

Vedi [`components.md`](./components.md) per varianti, stati e pattern ARIA.

## Usi vietati

- Hex o rgb **hardcoded** in componenti app (`#1c2736`, `#fff`, ecc.)
- `foregroundSubtle` per testo corpo lungo (contrasto insufficiente per AA)
- Accent su accent (CTA multiple competing)
- Ombre `lg` su ogni card (solo modali / overlay)
- Icone da set senza licenza compatibile o loghi squadre reali non licenziati
- Illustration stock o mascotte cartoon (vedi `illustration.avoid`)
- Colori semantici invertiti (es. `danger` per successo)

## Contrasto — verifica

```typescript
import { meetsWcagContrast, accessibleTextPairs } from "@fantappero/ui";
```

I pair in `accessibleTextPairs` sono testati in CI (`packages/ui/src/tokens.test.ts`).

Soglie WCAG 2.x:

- Testo normale: **4.5:1** (AA)
- Testo grande / UI component: **3:1** (AA)

## Internazionalizzazione (futura)

- Token e CSS restano agnostici alla lingua
- Copy utente nelle app, non nel package UI
- `lang="it"` sul documento HTML; attributi ARIA in italiano per ora

## Checklist PR UI

- [ ] Nessun colore hardcoded fuori da `packages/ui`
- [ ] Token semantici per spacing, radius, typography
- [ ] Stati loading / empty / error / success / forbidden gestiti
- [ ] Contrasto AA su nuove coppie testo/sfondo (test se necessario)
- [ ] Icone solo da set approvato (Lucide)
