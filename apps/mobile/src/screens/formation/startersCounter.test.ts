import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { palette } from "../../../../../packages/ui/src/tokens/palette.ts";
import {
  STARTERS_COUNTER_COLOR_TOKEN,
  startersCounterTone,
} from "./startersCounter.ts";

// Valori di `darkColors` e `lightColors` (packages/ui/src/tokens/colorSchemes.ts): il file non si
// importa qui perché i suoi import `.js` non girano nei test `node:test` senza il bundle.
const darkColors = {
  background: palette.pitch800,
  backgroundElevated: palette.pitch700,
  foreground: palette.ivory100,
  success: palette.success500,
};
const lightColors = {
  background: palette.cloud50,
  backgroundElevated: "#ffffff",
  foreground: "#0b162b",
  success: palette.success600,
};

/** Rapporto di contrasto WCAG fra due colori `#rrggbb`. */
function contrast(a: string, b: string): number {
  const luminance = (hex: string): number => {
    const [r, g, bl] = [1, 3, 5].map((start) => {
      const channel = Number.parseInt(hex.slice(start, start + 2), 16) / 255;
      return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    }) as [number, number, number];
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

describe("contatore dei titolari «0/11» (Rosario 27/11)", () => {
  it("sotto la soglia degli 11 è «incompleto», a 11 è «completo»", () => {
    assert.equal(startersCounterTone(0, 11), "incomplete");
    assert.equal(startersCounterTone(10, 11), "incomplete");
    assert.equal(startersCounterTone(11, 11), "complete");
  });

  it("sotto la soglia prende il colore del testo del tema, non il nero di sistema", () => {
    assert.equal(STARTERS_COUNTER_COLOR_TOKEN.incomplete, "foreground");
    assert.equal(STARTERS_COUNTER_COLOR_TOKEN.complete, "success");
  });

  it("nel tema scuro il testo è chiaro e si legge sul fondo scuro", () => {
    const color = darkColors[STARTERS_COUNTER_COLOR_TOKEN.incomplete];
    // Bianco o quasi: più chiaro del fondo, non il nero che spariva.
    assert.ok(contrast(color, "#ffffff") < 1.2, `${color} dovrebbe essere quasi bianco`);
    assert.ok(contrast(color, darkColors.background) >= 7, "AAA sul fondo scuro");
    assert.ok(contrast(color, darkColors.backgroundElevated) >= 4.5, "AA anche sulle schede");
    // Il nero di sistema, com'era prima, non passava.
    assert.ok(contrast("#000000", darkColors.background) < 1.3);
  });

  it("nel tema chiaro resta leggibile", () => {
    const color = lightColors[STARTERS_COUNTER_COLOR_TOKEN.incomplete];
    assert.ok(contrast(color, lightColors.background) >= 7);
    assert.ok(contrast(color, lightColors.backgroundElevated) >= 7);
  });

  it("anche il verde di «completo» si legge in entrambi i temi (testo grande, 3:1)", () => {
    const complete = STARTERS_COUNTER_COLOR_TOKEN.complete;
    assert.ok(contrast(darkColors[complete], darkColors.background) >= 3);
    assert.ok(contrast(lightColors[complete], lightColors.background) >= 3);
  });
});
