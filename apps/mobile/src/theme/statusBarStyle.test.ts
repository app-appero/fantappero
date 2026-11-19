import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { palette } from "../../../../packages/ui/src/tokens/palette.ts";
import { statusBarStyleForBackground } from "./statusBarStyle.ts";

describe("statusBarStyleForBackground", () => {
  it("usa icone scure sugli sfondi del tema chiaro", () => {
    // `lightColors.background` e `lightColors.backgroundElevated` (colorSchemes.ts).
    assert.equal(statusBarStyleForBackground(palette.cloud50, "light"), "dark");
    assert.equal(statusBarStyleForBackground("#ffffff", "light"), "dark");
  });

  it("usa icone chiare sugli sfondi del tema scuro", () => {
    // `darkColors.background` e `darkColors.backgroundElevated` (colorSchemes.ts).
    assert.equal(statusBarStyleForBackground(palette.pitch800, "dark"), "light");
    assert.equal(statusBarStyleForBackground(palette.pitch700, "dark"), "light");
  });

  it("legge anche la forma corta #rgb e le maiuscole", () => {
    assert.equal(statusBarStyleForBackground("#FFF", "light"), "dark");
    assert.equal(statusBarStyleForBackground("#000", "dark"), "light");
  });

  it("decide sul contrasto, non su una soglia a metà", () => {
    // Grigio medio: il nero ha più contrasto del bianco.
    assert.equal(statusBarStyleForBackground("#808080", "light"), "dark");
    // Il blu del marchio è scuro abbastanza da volere icone chiare.
    assert.equal(statusBarStyleForBackground(palette.cobalt700, "dark"), "light");
  });

  it("con un colore che non sa leggere torna al valore di riserva", () => {
    assert.equal(statusBarStyleForBackground("rgba(0,0,0,0.5)", "dark"), "dark");
    assert.equal(statusBarStyleForBackground("transparent", "light"), "light");
    assert.equal(statusBarStyleForBackground("", "light"), "light");
  });
});
