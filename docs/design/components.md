# Componenti UI (EPUI-02)

Primitive presentazionali condivise in `@fantappero/ui`. **Nessun testo di dominio** nei componenti: titoli, label, messaggi e opzioni arrivano sempre dalle app via props.

Import CSS (web/admin):

```css
@import "@fantappero/ui/theme.css";
```

## Token aggiuntivi

| Famiglia | Export TS | CSS |
| --- | --- | --- |
| Breakpoint | `breakpoints`, `breakpointUp`, `breakpointDown` | `--fa-bp-sm` … `--fa-bp-2xl` |
| Z-index | `zIndex` | `--fa-z-base` … `--fa-z-tooltip` |

Tutti i componenti consumano `--fa-*`; non duplicare colori o spacing nelle feature.

## Componenti

### Button

Varianti: `primary` (default), `secondary`, `ghost`, `danger`.  
Dimensioni: `sm`, `md` (default), `lg`.  
Stati: `loading`, `disabled` — entrambi bloccano l’interazione e impostano `aria-busy` / `aria-disabled`.

```tsx
import { Button } from "@fantappero/ui";

<Button variant="primary" loading={isSaving}>Salva</Button>
```

### Input / Select

Wrapper `fa-field` con label, hint ed errore collegati via `aria-describedby`.  
Errore: `aria-invalid="true"` + `role="alert"` sul messaggio.

```tsx
import { Input, Select } from "@fantappero/ui";

<Input label="Nome" error={errors.name} />
<Select label="Ruolo" options={[{ value: "c", label: "Centrocampista" }]} />
```

### Card

`Card`, `CardHeader` (prop `title` opzionale), `CardBody`, `CardFooter`.

### Badge

Varianti: `neutral`, `accent`, `success`, `warning`, `danger`.

### Tabs

Pattern WAI-ARIA: frecce sinistra/destra, Home/End sulla tablist.  
Controllato (`value` + `onValueChange`) o non controllato (`defaultValue`).

```tsx
import { Tabs, TabList, Tab, TabPanel } from "@fantappero/ui";

<Tabs defaultValue="a" aria-label="Sezione">
  <TabList>
    <Tab value="a">A</Tab>
    <Tab value="b">B</Tab>
  </TabList>
  <TabPanel value="a">…</TabPanel>
  <TabPanel value="b">…</TabPanel>
</Tabs>
```

### Modal

`open`, `onClose`, `title`, `footer` opzionale. Escape chiude; focus sul dialog all’apertura.  
Prop `closeLabel` per i18n (default italiano nel package: `"Chiudi"`).

### Toast

```tsx
import { ToastProvider, useToast } from "@fantappero/ui";

// Root app
<ToastProvider dismissLabel="Chiudi">
  <App />
</ToastProvider>

// Feature
const { push } = useToast();
push({ title: "Salvato", variant: "success" });
```

Regione live `aria-live="polite"`; auto-dismiss configurabile (`durationMs`, `0` = persistente).

### Table

`Table`, `TableHead`, `TableBody`, `TableRow`, `TableHeaderCell`, `TableCell`.  
Prop `compact` per tabelle fantasy dense.

### Skeleton / EmptyState

`Skeleton` — varianti `text`, `title`, `avatar`, `block`; `role="status"`, `aria-busy`.  
`EmptyState` — `title`, `description`, slot `icon` e `actions`.

### UiStatePanel (EPUI-01)

Resta il componente per stati pagina (`loading`, `empty`, `error`, `success`, `forbidden`).

## Stati e accessibilità

| Componente | Focus | Stati |
| --- | --- | --- |
| Button | `:focus-visible` + `--fa-shadow-focus` | hover, disabled, loading |
| Input/Select | bordo accent + focus ring | hover, disabled, error |
| Tabs | roving `tabIndex` | selected, disabled |
| Modal | focus trap leggero + Escape | backdrop click |
| Toast | pulsante dismiss etichettato | live region |

Test automatici: `packages/ui/src/components/design-system.test.tsx`.

## Anteprima locale

`apps/web/src/DesignSystemShowcase.tsx` — showcase non-produttivo sulla pagina health.

## Checklist PR

- [ ] Copy utente nelle app, non in `@fantappero/ui`
- [ ] Nessun hex hardcoded fuori da `packages/ui`
- [ ] Nuovi componenti esportati da `packages/ui/src/index.ts`
- [ ] Stili solo in `components.css` / token esistenti
- [ ] Test markup + ARIA per comportamenti principali
