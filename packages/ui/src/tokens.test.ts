import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { accessibleTextPairs, breakpoints, colors, palette, spacing, theme, typography, zIndex } from "./index.js";
import { darkColors, lightColors } from "./tokens/colorSchemes.js";
import { contrastRatio, meetsWcagContrast } from "./accessibility/contrast.js";

const readCss = (name: string) => readFileSync(new URL(`./css/${name}`, import.meta.url), "utf8");

function customProperties(block: string): Record<string, string> {
  return Object.fromEntries(
    [...block.matchAll(/(--fa-[\w-]+):\s*([^;]+);/g)].map((match) => [match[1], (match[2] ?? "").trim()]),
  );
}

/**
 * Token come li vede il browser. Tema chiaro: prima il blocco chiaro, poi quello di base.
 * Tema scuro: solo il blocco di base.
 */
function tokenResolver(scheme: "light" | "dark") {
  const tokensCss = readCss("tokens.css");
  const base = customProperties(/\[data-theme="fantappero"\]\s*\{([^}]*)\}/.exec(tokensCss)?.[1] ?? "");
  const light =
    scheme === "light"
      ? customProperties(/\[data-color-scheme="light"\]\s*\{([^}]*)\}/.exec(tokensCss)?.[1] ?? "")
      : {};
  const resolve = (value: string): string => {
    const reference = /^var\((--fa-[\w-]+)\)$/.exec(value.trim())?.[1];
    if (!reference) {
      return value.trim();
    }
    return resolve(light[reference] ?? base[reference] ?? "");
  };
  return resolve;
}

const lightTokenResolver = () => tokenResolver("light");

/** Sfondi su cui si scrive il testo (gli stessi nomi in entrambi i temi). */
const CSS_BACKGROUNDS = [
  "--fa-color-background",
  "--fa-color-background-subtle",
  "--fa-color-background-elevated",
] as const;

/** Gli stessi tre sfondi nell'app (React Native). */
const APP_BACKGROUNDS = ["background", "backgroundSubtle", "backgroundElevated"] as const;

describe("design tokens", () => {
  it("exposes required scaffold keys", () => {
    expect(colors.ok).toBeTruthy();
    expect(colors.muted).toBeTruthy();
    expect(spacing.md).toBe(16);
    expect(typeof typography.fontFamily).toBe("string");
    expect(typography.fontSize.xl).toBeTruthy();
  });

  it("exposes breakpoints and z-index layers", () => {
    expect(breakpoints.md).toBe(768);
    expect(zIndex.modal).toBeGreaterThan(zIndex.overlay);
    expect(theme.breakpoints.lg).toBe(1024);
    expect(theme.zIndex.toast).toBe(500);
  });

  it("aggregates semantic groups in theme", () => {
    expect(theme.colors.background).toBe(colors.background);
    expect(theme.radius.md).toBeGreaterThanOrEqual(0);
    expect(theme.visualPrinciples.positioning.length).toBeGreaterThan(0);
  });

  it("validates accessible text pairs for WCAG AA", () => {
    for (const pair of accessibleTextPairs) {
      expect(
        meetsWcagContrast(pair.foreground, pair.background, {
          largeText: "largeText" in pair ? pair.largeText : false,
        }),
        `Pair "${pair.label}" failed contrast check`,
      ).toBe(true);
    }
  });

  it("validates accent on elevated surface for UI component contrast", () => {
    expect(
      meetsWcagContrast(colors.accent, colors.backgroundElevated, { largeText: true }),
    ).toBe(true);
  });
});

describe("tema chiaro (CSS)", () => {
  const resolve = lightTokenResolver();

  it("il verde «successo» si legge sugli sfondi chiari (almeno 4,5:1)", () => {
    const success = resolve("var(--fa-color-success)");
    for (const background of CSS_BACKGROUNDS) {
      const ratio = contrastRatio(success, resolve(`var(${background})`));
      expect(ratio, `${success} su ${background}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("l'ambra «attenzione» si legge sugli sfondi chiari (almeno 4,5:1)", () => {
    const warning = resolve("var(--fa-color-warning)");
    for (const background of CSS_BACKGROUNDS) {
      const ratio = contrastRatio(warning, resolve(`var(${background})`));
      expect(ratio, `${warning} su ${background}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("sul fondo ambra il testo chiaro si legge (banner di impersonificazione)", () => {
    // `.fa-impersonation-banner` (apps/web): fondo --fa-color-warning, testo --fa-pitch-900.
    const ratio = contrastRatio(resolve("var(--fa-pitch-900)"), resolve("var(--fa-color-warning)"));
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("il titolo del pannello «non autorizzato» usa l'ambra leggibile", () => {
    const themeCss = readCss("theme.css");
    // Nessuna eccezione per il tema chiaro: basta il token.
    expect(themeCss).not.toMatch(/\[data-color-scheme="light"\]\s*\.fa-state-panel--forbidden/);
    const title = /\.fa-state-panel--forbidden\s+\.fa-state-panel__title\s*\{[^}]*?color:\s*([^;]+);/.exec(themeCss)?.[1] ?? "";
    expect(contrastRatio(resolve(title), resolve("var(--fa-color-background-elevated)"))).toBeGreaterThanOrEqual(4.5);
  });

  it("il titolo del pannello di successo usa un colore leggibile", () => {
    const themeCss = readCss("theme.css");
    const lightOverride = /\[data-color-scheme="light"\]\s*\.fa-state-panel--success\s+\.fa-state-panel__title\s*\{[^}]*?color:\s*([^;]+);/.exec(themeCss)?.[1];
    const baseRule = /(?:^|\n)\.fa-state-panel--success\s+\.fa-state-panel__title\s*\{[^}]*?color:\s*([^;]+);/.exec(themeCss)?.[1];
    const title = resolve(lightOverride ?? baseRule ?? "");
    // Il pannello ha come fondo la superficie rialzata.
    expect(contrastRatio(title, resolve("var(--fa-color-background-elevated)"))).toBeGreaterThanOrEqual(4.5);
  });

  it("la tab selezionata resta bianca anche al passaggio del mouse", () => {
    // «.fa-tab:hover:not(:disabled)» è più specifica della tab selezionata e la scuriva sul gradiente.
    const rule = /\.fa-tab\[aria-selected="true"\]:hover:not\(:disabled\)\s*\{([^}]*)\}/.exec(readCss("components.css"))?.[1] ?? "";
    expect(rule).toContain("color: var(--fa-color-on-brand)");
  });
});

describe("tema scuro (CSS)", () => {
  const resolve = tokenResolver("dark");

  it("l'ambra «attenzione» resta #e6a700, oltre 8:1 sugli sfondi scuri", () => {
    const warning = resolve("var(--fa-color-warning)");
    expect(warning).toBe("#e6a700");
    for (const background of CSS_BACKGROUNDS) {
      const ratio = contrastRatio(warning, resolve(`var(${background})`));
      expect(ratio, `${warning} su ${background}`).toBeGreaterThanOrEqual(8);
    }
  });
});

describe("campo della Formazione: «senza voto»", () => {
  /** Colori del gradiente di una regola di layout.css, nell'ordine. */
  function gradientStops(selector: RegExp): string[] {
    const rule = new RegExp(`${selector.source}\\s*\\{([^}]*)\\}`).exec(readCss("layout.css"))?.[1] ?? "";
    expect(rule, `regola ${selector.source}`).toContain("color: #fff;");
    const gradient = /linear-gradient\(([^)]*)\)/.exec(rule)?.[1] ?? "";
    return [...gradient.matchAll(/#[0-9a-fA-F]{6}/g)].map((match) => match[0]);
  }

  // Colori fissi, non token: sono gli stessi nel tema chiaro e in quello scuro.
  it("il nome bianco del titolare senza voto si legge su tutto il gradiente (almeno 4,5:1)", () => {
    const stops = gradientStops(/\.fa-pitch-player--sv \.fa-pitch-player__name/);
    expect(stops).toEqual(["#7c3aed", "#9333ea"]);
    for (const stop of stops) {
      expect(contrastRatio("#ffffff", stop), `#ffffff su ${stop}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("anche il voto «s.v.» bianco sullo stesso viola si legge (almeno 4,5:1)", () => {
    const stops = gradientStops(/\.fa-pitch-player__score--sv/);
    expect(stops).toEqual(["#6d28d9", "#9333ea"]);
    for (const stop of stops) {
      expect(contrastRatio("#ffffff", stop), `#ffffff su ${stop}`).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe("ambra «attenzione» nell'app", () => {
  it("nel tema chiaro si legge come testo sugli sfondi (almeno 4,5:1)", () => {
    for (const background of APP_BACKGROUNDS) {
      const ratio = contrastRatio(lightColors.warning, lightColors[background]);
      expect(ratio, `${lightColors.warning} su ${background}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("quando fa da fondo (badge di stato, ruolo D, stati del mercato) il testo sopra si legge", () => {
    for (const scheme of [lightColors, darkColors]) {
      // StatusBadge e RoleBadge scrivono in accentContrast, le etichette del mercato in background.
      for (const text of ["accentContrast", "background"] as const) {
        const ratio = contrastRatio(scheme[text], scheme.warning);
        expect(ratio, `${scheme[text]} su ${scheme.warning}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("il tema scuro resta invariato", () => {
    expect(darkColors.warning).toBe(palette.warning500);
    for (const background of APP_BACKGROUNDS) {
      expect(contrastRatio(darkColors.warning, darkColors[background])).toBeGreaterThanOrEqual(8);
    }
  });
});

describe("campo della Formazione: alone «In dubbio» (1.5)", () => {
  const layout = readCss("layout.css");

  it("il token arancione è lo stesso nei due temi", () => {
    expect(tokenResolver("dark")("var(--fa-halo-doubt)")).toBe("#ea580c");
    expect(tokenResolver("light")("var(--fa-halo-doubt)")).toBe("#ea580c");
    expect(tokenResolver("light")("var(--fa-halo-doubt-strong)")).toBe("#c2410c");
  });

  it("il pallino della legenda si vede sugli sfondi chiari e scuri (almeno 3:1)", () => {
    for (const scheme of ["light", "dark"] as const) {
      const resolve = tokenResolver(scheme);
      const doubt = resolve("var(--fa-halo-doubt)");
      for (const background of CSS_BACKGROUNDS) {
        const ratio = contrastRatio(doubt, resolve(`var(${background})`));
        expect(ratio, `${doubt} su ${background} (${scheme})`).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("il nome bianco sull'arancione si legge (almeno 4,5:1)", () => {
    const rule = /\.fa-pitch-player--doubt \.fa-pitch-player__name\s*\{([^}]*)\}/.exec(layout)?.[1] ?? "";
    expect(rule).toContain("var(--fa-halo-doubt-strong");
    expect(rule).toContain("color: #fff;");
    const strong = tokenResolver("dark")("var(--fa-halo-doubt-strong)");
    expect(contrastRatio("#ffffff", strong)).toBeGreaterThanOrEqual(4.5);
  });

  it("è ben distinto dal giallo «Possibile panchina» e dal rosso «Espulso»", () => {
    const doubt = tokenResolver("dark")("var(--fa-halo-doubt)");
    // Giallo della panchina: con l'arancione serve una differenza netta di luminosità.
    expect(contrastRatio(doubt, "#facc15")).toBeGreaterThanOrEqual(2);
    expect(doubt).not.toBe("#ef4444");
    expect(layout).toMatch(/\.fa-formation-legend__dot--doubt\s*\{[^}]*--fa-halo-doubt/);
    expect(layout).toMatch(/\.fa-pitch-player--doubt \.fa-pitch-player__card\s*\{[^}]*--fa-halo-doubt/);
  });
});

