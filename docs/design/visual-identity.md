# Identità visiva FantApperò (EPUI-01)

Direzione visiva condivisa tra **web app**, **pannello amministrativo** (stesso stack React) e **mobile** (token programmatici).

Implementazione: [`packages/ui`](../../packages/ui) — token TypeScript, CSS custom properties e primitive presentazionali.

## Posizionamento

| Attributo | Descrizione |
| --- | --- |
| Moderno | Layout pulito, tipografia IBM Plex, accent elettrico su sfondo scuro |
| Accattivante | Gradiente pitch sottile, stati colore chiari, gerarchia netta |
| Premium | Spaziatura generosa negli stati vuoto/errore, ombre soft, motion sobria |
| Pulito | Nessun clutter, dati fantasy in mono, icone lineari Lucide (MIT) |

## Moodboard (concettuale)

- **Notte europea** — sfondo pitch navy (`#0f1419`) con alone `#1c2736`
- **Ivory caldo** — testo primario `#f4f1ea`, non bianco puro
- **Accent elettrico** — CTA e link `#2f6fed`
- **Feedback sportivo** — successo verde, warning ambra, errore rosso controllato
- **Illustrazioni** — forme geometriche, linee da campo, niente foto stock o loghi club senza licenza

Principi codificati in `visualPrinciples` (`packages/ui/src/tokens/principles.ts`).

## Palette semantica

Usare sempre i **token semantici** (`colors.*`), mai hex nelle schermate.

| Token | Uso |
| --- | --- |
| `background` / `backgroundElevated` | Sfondo pagina e card |
| `foreground` / `foregroundMuted` | Testo primario e secondario |
| `accent` | Azioni primarie, link, focus |
| `success` / `warning` / `danger` | Esito, attenzione, errore |
| `border` | Separatori e contenitori |

Contrasto verificato automaticamente in `accessibleTextPairs` (WCAG **AA** minimo).

## Tipografia

- **Sans:** IBM Plex Sans (SIL OFL) — UI, titoli, copy
- **Mono:** IBM Plex Mono — punteggi, crediti, statistiche tabellari

Ruoli testo: `textRoles.display | title | heading | body | label | caption | stat`.

## Iconografia

Set approvato: **[Lucide](https://lucide.dev/)** (`lucide-react`, licenza MIT).

Dimensioni token: `iconography.size.sm | md | lg | xl`. Stroke 1.75px.

## Raggi, ombre, spaziatura

| Famiglia | Token | Valori chiave |
| --- | --- | --- |
| Radius | `radius.sm` … `pill` | 4–16px + pill |
| Shadow | `shadows.sm` … `lg` | Elevazione dark UI |
| Spacing | `spacing.xs` … `3xl` | Griglia 4px |
| Density | `density.compact \| comfortable \| spacious` | Tabelle vs onboarding |
| Breakpoint | `breakpoints.sm` … `2xl` | Mobile-first (640–1536px) |
| Z-index | `zIndex.base` … `tooltip` | Layer modal, toast, overlay |

Componenti web: [`docs/design/components.md`](./components.md) (EPUI-02).

## Web e admin

Import globale:

```css
@import "@fantappero/ui/theme.css";
```

Attributi consigliati sul root layout:

```html
<html lang="it" data-theme="fantappero">
<body data-surface="app">   <!-- oppure data-surface="admin" -->
```

Le CSS custom properties (`--fa-*`) sono la fonte unica per il web; i token TS restano allineati.

## Mobile

Consumare `theme` da `@fantappero/ui` (StyleSheet). Stessi valori semantici, niente hex locali.

## Riferimenti

- Linee guida d'uso: [`usage-guidelines.md`](usage-guidelines.md)
- Package UI: [`packages/ui/README.md`](../../packages/ui/README.md)
- Monorepo: [`ADR-0003`](../adr/ADR-0003-monorepo.md)
