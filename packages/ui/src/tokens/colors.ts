import { palette } from "./palette.js";

/** Semantic color roles — use these in UI instead of raw hex values. */
export const colors = {
  background: palette.pitch800,
  backgroundSubtle: palette.pitch900,
  backgroundElevated: palette.pitch700,
  backgroundGradientStop: palette.pitch700,

  foreground: palette.ivory100,
  foregroundMuted: palette.slate300,
  foregroundSubtle: palette.slate400,

  accent: palette.electric500,
  accentHover: palette.electric400,
  accentMuted: palette.electric300,

  border: palette.pitch600,
  borderStrong: palette.pitch500,

  success: palette.success500,
  successMuted: palette.success400,
  warning: palette.warning500,
  warningMuted: palette.warning400,
  danger: palette.danger500,
  dangerMuted: palette.danger400,

  focusRing: palette.focusRing,

  /** @deprecated Use `foregroundMuted` — kept for EP01-01 scaffold compatibility. */
  muted: palette.slate300,
  /** @deprecated Use `success` — kept for EP01-01 scaffold compatibility. */
  ok: palette.success500,
} as const;

export type ColorToken = keyof typeof colors;

/** Pairs validated for WCAG AA in contrast.test.ts */
export const accessibleTextPairs = [
  { foreground: colors.foreground, background: colors.background, label: "body" },
  {
    foreground: colors.foregroundMuted,
    background: colors.background,
    label: "secondary",
  },
  { foreground: colors.accent, background: colors.background, label: "accent-link", largeText: true },
  { foreground: colors.success, background: colors.background, label: "success", largeText: true },
  { foreground: colors.danger, background: colors.background, label: "danger", largeText: true },
  { foreground: colors.warning, background: colors.background, label: "warning", largeText: true },
  {
    foreground: colors.foreground,
    background: colors.backgroundElevated,
    label: "elevated-body",
  },
] as const;
