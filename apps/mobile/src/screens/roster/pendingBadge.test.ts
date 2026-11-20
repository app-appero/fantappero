import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { contrastRatio } from "../../../../../packages/ui/src/accessibility/contrast.ts";
import { PENDING_BADGE_COLORS } from "./pendingBadge.ts";

const readUiCss = (name: string) =>
  readFileSync(new URL(`../../../../../packages/ui/src/css/${name}`, import.meta.url), "utf8");

describe("badge «In attesa (fuori rosa)» (QA 19-20/11)", () => {
  it("testo e fondo arrivano almeno a 4,5:1", () => {
    assert.ok(contrastRatio(PENDING_BADGE_COLORS.text, PENDING_BADGE_COLORS.background) >= 4.5);
  });

  it("ha gli stessi colori del badge «In attesa» del web", () => {
    const rule = /\.fa-badge--warning\s*\{([^}]*)\}/.exec(readUiCss("components.css"))?.[1] ?? "";
    const background = /background-color:\s*var\((--fa-[\w-]+)\)/.exec(rule)?.[1] ?? "";
    const token = new RegExp(`${background}:\\s*(#[0-9a-fA-F]{6})`).exec(readUiCss("tokens.css"))?.[1];
    assert.equal(token?.toLowerCase(), PENDING_BADGE_COLORS.background);
    assert.equal(/(?:^|\s)color:\s*(#[0-9a-fA-F]{6})/.exec(rule)?.[1]?.toLowerCase(), PENDING_BADGE_COLORS.text);
  });
});
