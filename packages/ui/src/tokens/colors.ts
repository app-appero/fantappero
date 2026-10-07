import {
  darkColors,
  lightColors,
  type AppColors,
  type ResolvedColorScheme,
} from "./colorSchemes.js";

/** Semantic color roles — use these in UI instead of raw hex values. */
export const colors: AppColors = { ...darkColors };

let activeScheme: ResolvedColorScheme = "dark";

export function getActiveColorScheme(): ResolvedColorScheme {
  return activeScheme;
}

/** Switches the shared palette in place so the next render reads the new colors. */
export function applyColorScheme(scheme: ResolvedColorScheme): void {
  activeScheme = scheme;
  const next = scheme === "light" ? lightColors : darkColors;
  (Object.keys(next) as (keyof AppColors)[]).forEach((key) => {
    colors[key] = next[key];
  });
}

export type ColorToken = keyof AppColors;

/** Pairs validated for WCAG AA in contrast.test.ts */
export const accessibleTextPairs = [
  { foreground: darkColors.foreground, background: darkColors.background, label: "body" },
  {
    foreground: darkColors.foregroundMuted,
    background: darkColors.background,
    label: "secondary",
  },
  {
    foreground: darkColors.accent,
    background: darkColors.background,
    label: "accent-link",
    largeText: true,
  },
  {
    foreground: darkColors.success,
    background: darkColors.background,
    label: "success",
    largeText: true,
  },
  {
    foreground: darkColors.danger,
    background: darkColors.background,
    label: "danger",
    largeText: true,
  },
  {
    foreground: darkColors.warning,
    background: darkColors.background,
    label: "warning",
    largeText: true,
  },
  {
    foreground: darkColors.foreground,
    background: darkColors.backgroundElevated,
    label: "elevated-body",
  },
] as const;
