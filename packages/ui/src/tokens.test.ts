import { describe, expect, it } from "vitest";
import { accessibleTextPairs, breakpoints, colors, spacing, theme, typography, zIndex } from "./index.js";
import { meetsWcagContrast } from "./accessibility/contrast.js";

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
