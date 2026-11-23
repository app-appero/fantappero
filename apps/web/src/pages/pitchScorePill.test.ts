import { describe, expect, it } from "vitest";
import layoutCss from "../../../../packages/ui/src/css/layout.css?raw";
import stylesCss from "../styles.css?raw";

type CssRule = { selector: string; body: string };

/** Regole (anche dentro le media query) il cui selettore nomina la pillola del voto sul campo. */
function scorePillRules(css: string): CssRule[] {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...withoutComments.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .map((match) => ({ selector: (match[1] ?? "").trim(), body: match[2] ?? "" }))
    .filter((rule) => rule.selector.includes(".fa-pitch-player__score"));
}

function ruleFor(css: string, selector: string): CssRule {
  const rule = scorePillRules(css).find((candidate) => candidate.selector === selector);
  expect(rule, `manca la regola ${selector}`).toBeDefined();
  return rule as CssRule;
}

describe("campo: colori della pillola del voto (QA 22→23/11)", () => {
  it("layout.css dà a «s.v.» e «provvisorio» un gradiente e al voto definitivo il bianco", () => {
    expect(ruleFor(layoutCss, ".fa-pitch-player__score--sv").body).toContain("linear-gradient(135deg, #6d28d9, #9333ea)");
    expect(ruleFor(layoutCss, ".fa-pitch-player__score--provisional").body).toContain(
      "linear-gradient(135deg, #2563eb, #3b82f6)",
    );
    const final = ruleFor(layoutCss, ".fa-pitch-player__score--final").body;
    expect(final).toMatch(/background(?:-color)?: #ffffff;/);
    expect(final).toContain("color: #11162b;");
  });

  it("il sito non azzera i gradienti con «background:» (s.v. grigio scuro invece che viola)", () => {
    const rules = scorePillRules(stylesCss);
    expect(rules.length).toBeGreaterThan(0);
    for (const rule of rules) {
      // styles.css viene dopo layout.css: lo shorthand rimetterebbe background-image a «none».
      expect(rule.body, rule.selector).not.toMatch(/(?:^|[;\s])background\s*:/);
    }
    const base = rules.find((rule) => rule.selector.startsWith(".fa-pitch-player__score:not("));
    expect(base?.body).toContain("background-color: rgba(8, 12, 30, 0.78);");
  });

  it("il fondo blu notte e il testo bianco del sito non coprono il voto definitivo", () => {
    for (const rule of scorePillRules(stylesCss)) {
      const setsColors = /(?:^|[;\s])(?:color|background-color)\s*:/.test(rule.body);
      if (setsColors && !rule.selector.includes("--sv") && !rule.selector.includes("--provisional")) {
        expect(rule.selector, "la regola deve lasciare stare .fa-pitch-player__score--final").toContain(
          ":not(.fa-pitch-player__score--final)",
        );
      }
    }
  });
});
