import { contrastRatio } from "@fantappero/ui";
import { describe, expect, it } from "vitest";
import componentsCss from "../../../../packages/ui/src/css/components.css?raw";
import tokensCss from "../../../../packages/ui/src/css/tokens.css?raw";
import stylesCss from "../styles.css?raw";
import { hrefForLifecycleAction } from "./LeagueSeasonPanel";

describe("hrefForLifecycleAction", () => {
  it("porta le rose su Mercato → Rosa, non in Amministrazione", () => {
    expect(hrefForLifecycleAction("teams")).toBe("/rosa");
  });

  it("porta il calendario sui Turni", () => {
    expect(hrefForLifecycleAction("calendar")).toBe("/turni?tab=calendario");
  });

  it("lascia regolamento e partecipanti nella pagina di setup", () => {
    expect(hrefForLifecycleAction("rules")).toBeNull();
    expect(hrefForLifecycleAction("members")).toBeNull();
  });
});

type Rgb = [number, number, number];

function toRgb(hex: string): Rgb {
  const value = hex.trim().replace("#", "");
  return [0, 2, 4].map((index) => Number.parseInt(value.slice(index, index + 2), 16)) as Rgb;
}

/** `top` sopra `bottom` con opacità `alpha` (vale anche per `color-mix` in sRGB). */
function blend(top: string, bottom: string, alpha: number): string {
  const a = toRgb(top);
  const b = toRgb(bottom);
  return `#${a
    .map((channel, index) => Math.round(channel * alpha + b[index]! * (1 - alpha)).toString(16).padStart(2, "0"))
    .join("")}`;
}

function ruleBody(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(css)?.[1] ?? "";
}

function declaration(body: string, property: string): string | null {
  return new RegExp(`(?:^|[;\\s])${property}:\\s*([^;]+);`).exec(body)?.[1]?.trim() ?? null;
}

function customProperties(block: string): Record<string, string> {
  return Object.fromEntries(
    [...block.matchAll(/(--fa-[\w-]+):\s*([^;]+);/g)].map((match) => [match[1], (match[2] ?? "").trim()]),
  );
}

/** Token del tema scuro (blocco di base) o chiaro (blocco chiaro sopra quello di base). */
function tokenResolver(scheme: "dark" | "light") {
  const base = customProperties(/\[data-theme="fantappero"\]\s*\{([^}]*)\}/.exec(tokensCss)?.[1] ?? "");
  const light =
    scheme === "light"
      ? customProperties(/\[data-color-scheme="light"\]\s*\{([^}]*)\}/.exec(tokensCss)?.[1] ?? "")
      : {};
  const resolve = (value: string): string => {
    const match = /^var\((--fa-[\w-]+)(?:,\s*([^)]+))?\)$/.exec(value.trim());
    if (!match) {
      return value.trim();
    }
    const next = light[match[1]!] ?? base[match[1]!] ?? match[2];
    return next ? resolve(next) : "";
  };
  return resolve;
}

describe("passaggi in attesa del setup lega: contrasto (QA 19-20/11)", () => {
  // «In attesa» e «Completa prima il passaggio precedente.» si leggevano a circa 2,6:1
  // perché la riga bloccata aveva `opacity: 0.65` sopra testo già secondario.
  const locked = ruleBody(stylesCss, ".fa-lifecycle-checklist__item--locked");
  const opacity = Number(declaration(locked, "opacity") ?? "1");
  const messageColor =
    declaration(
      ruleBody(stylesCss, ".fa-lifecycle-checklist__item--locked .fa-lifecycle-checklist__message"),
      "color",
    ) ?? "var(--fa-color-foreground)";
  const containerBackground = declaration(ruleBody(stylesCss, ".fa-lifecycle-checklist"), "background") ?? "";
  const badge = ruleBody(componentsCss, ".fa-badge--neutral");

  for (const scheme of ["dark", "light"] as const) {
    it(`badge e messaggio arrivano almeno a 4,5:1 nel tema ${scheme === "dark" ? "scuro" : "chiaro"}`, () => {
      const resolve = tokenResolver(scheme);
      const mix = /^color-mix\(in srgb, (var\([^)]+\)) (\d+)%, (var\([^)]+\))\)$/.exec(containerBackground);
      expect(mix, containerBackground).not.toBeNull();
      const container = blend(resolve(mix![1]!), resolve(mix![3]!), Number(mix![2]) / 100);

      const badgeBackground = blend(resolve(declaration(badge, "background-color") ?? ""), container, opacity);
      const badgeText = blend(resolve(declaration(badge, "color") ?? ""), container, opacity);
      const message = blend(resolve(messageColor), container, opacity);

      expect(contrastRatio(badgeText, badgeBackground), `«In attesa» ${badgeText} su ${badgeBackground}`).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(message, container), `messaggio ${message} su ${container}`).toBeGreaterThanOrEqual(4.5);
    });
  }
});
