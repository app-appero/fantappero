import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { contrastRatio } from "../../../../../packages/ui/src/accessibility/contrast.ts";
import { PENDING_BADGE_COLORS, PENDING_BADGE_LABEL } from "./pendingBadge.ts";

const readUiCss = (name: string) =>
  readFileSync(new URL(`../../../../../packages/ui/src/css/${name}`, import.meta.url), "utf8");

describe("badge «In esubero» (QA 19-20/11)", () => {
  it("testo e fondo arrivano almeno a 4,5:1", () => {
    assert.ok(contrastRatio(PENDING_BADGE_COLORS.text, PENDING_BADGE_COLORS.background) >= 4.5);
  });

  it("ha gli stessi colori del badge «In esubero» del web", () => {
    const rule = /\.fa-badge--warning\s*\{([^}]*)\}/.exec(readUiCss("components.css"))?.[1] ?? "";
    const background = /background-color:\s*var\((--fa-[\w-]+)\)/.exec(rule)?.[1] ?? "";
    const token = new RegExp(`${background}:\\s*(#[0-9a-fA-F]{6})`).exec(readUiCss("tokens.css"))?.[1];
    assert.equal(token?.toLowerCase(), PENDING_BADGE_COLORS.background);
    assert.equal(/(?:^|\s)color:\s*(#[0-9a-fA-F]{6})/.exec(rule)?.[1]?.toLowerCase(), PENDING_BADGE_COLORS.text);
  });
});

describe("Rosa: il giocatore in esubero si legge «In esubero» (Rosario, 23/11)", () => {
  const summarySource = readFileSync(new URL("./RosterFilledSummary.tsx", import.meta.url), "utf8");

  it("la scritta è «In esubero», la stessa del sito", () => {
    assert.equal(PENDING_BADGE_LABEL, "In esubero");
  });

  it("la Rosa mostra quella scritta e non più «In attesa (fuori rosa)»", () => {
    assert.match(summarySource, /\{PENDING_BADGE_LABEL\}/);
    assert.doesNotMatch(summarySource, /In attesa/);
  });

  it("accanto al badge resta il «?» che apre la risposta sull'esubero", () => {
    const row = /\{PENDING_BADGE_LABEL\}([\s\S]*?)<\/View>/.exec(summarySource)?.[1] ?? "";
    assert.match(row, /<FaqHelpButton[\s\S]*faqId=\{FAQ_HELP\.surplus\}/);
  });
});
