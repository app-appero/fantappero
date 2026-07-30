import { describe, expect, it } from "vitest";
import { contrastRatio, meetsWcagContrast, relativeLuminance } from "./contrast.js";

describe("WCAG contrast utilities", () => {
  it("rejects invalid hex for relativeLuminance", () => {
    expect(() => relativeLuminance("red")).toThrow(/Expected #RRGGBB/);
  });

  it("computes symmetric contrastRatio", () => {
    const ratio = contrastRatio("#ffffff", "#000000");
    expect(ratio).toBeGreaterThanOrEqual(20);
    expect(ratio).toBe(contrastRatio("#000000", "#ffffff"));
  });

  it("enforces AA thresholds in meetsWcagContrast", () => {
    expect(meetsWcagContrast("#ffffff", "#000000")).toBe(true);
    expect(meetsWcagContrast("#ffffff", "#000000", { largeText: true })).toBe(true);
    expect(meetsWcagContrast("#777777", "#888888")).toBe(false);
  });

  it("supports AAA level in meetsWcagContrast", () => {
    expect(meetsWcagContrast("#ffffff", "#000000", { level: "AAA" })).toBe(true);
    expect(meetsWcagContrast("#767676", "#ffffff", { level: "AAA" })).toBe(false);
  });
});
