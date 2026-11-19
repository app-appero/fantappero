import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { accessibleTextPairs, breakpoints, colors, spacing, theme, typography, zIndex } from "./index.js";
import { contrastRatio, meetsWcagContrast } from "./accessibility/contrast.js";

const readCss = (name: string) => readFileSync(new URL(`./css/${name}`, import.meta.url), "utf8");

function customProperties(block: string): Record<string, string> {
  return Object.fromEntries(
    [...block.matchAll(/(--fa-[\w-]+):\s*([^;]+);/g)].map((match) => [match[1], (match[2] ?? "").trim()]),
  );
}

/** Token del tema chiaro come li vede il browser: prima il blocco chiaro, poi quello di base. */
function lightTokenResolver() {
  const tokensCss = readCss("tokens.css");
  const base = customProperties(/\[data-theme="fantappero"\]\s*\{([^}]*)\}/.exec(tokensCss)?.[1] ?? "");
  const light = customProperties(/\[data-color-scheme="light"\]\s*\{([^}]*)\}/.exec(tokensCss)?.[1] ?? "");
  const resolve = (value: string): string => {
    const reference = /^var\((--fa-[\w-]+)\)$/.exec(value.trim())?.[1];
    if (!reference) {
      return value.trim();
    }
    return resolve(light[reference] ?? base[reference] ?? "");
  };
  return resolve;
}

const LIGHT_BACKGROUNDS = [
  "--fa-color-background",
  "--fa-color-background-subtle",
  "--fa-color-background-elevated",
] as const;

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
    for (const background of LIGHT_BACKGROUNDS) {
      const ratio = contrastRatio(success, resolve(`var(${background})`));
      expect(ratio, `${success} su ${background}`).toBeGreaterThanOrEqual(4.5);
    }
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
