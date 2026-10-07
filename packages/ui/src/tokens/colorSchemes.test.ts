import { describe, expect, it } from "vitest";
import { applyColorScheme, colors, getActiveColorScheme } from "./colors.js";
import { darkColors, lightColors, resolveColorScheme } from "./colorSchemes.js";

describe("resolveColorScheme", () => {
  it("keeps an explicit light or dark choice", () => {
    expect(resolveColorScheme("light", "dark")).toBe("light");
    expect(resolveColorScheme("dark", "light")).toBe("dark");
  });

  it("follows the system scheme and falls back to dark", () => {
    expect(resolveColorScheme("system", "light")).toBe("light");
    expect(resolveColorScheme("system", "dark")).toBe("dark");
    expect(resolveColorScheme("system", null)).toBe("dark");
    expect(resolveColorScheme("system", "unspecified")).toBe("dark");
  });
});

describe("applyColorScheme", () => {
  it("switches placeholders between white and a dark tone", () => {
    applyColorScheme("dark");
    expect(getActiveColorScheme()).toBe("dark");
    expect(colors.inputPlaceholder).toBe("#ffffff");
    expect(colors.background).toBe(darkColors.background);

    applyColorScheme("light");
    expect(colors.inputPlaceholder).toBe(lightColors.inputPlaceholder);
    expect(colors.background).toBe(lightColors.background);
    expect(colors.foreground).toBe(lightColors.foreground);

    applyColorScheme("dark");
  });
});
