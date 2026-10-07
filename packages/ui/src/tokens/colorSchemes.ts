import { palette } from "./palette.js";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedColorScheme = "light" | "dark";

export type AppColors = {
  background: string;
  backgroundSubtle: string;
  backgroundElevated: string;
  backgroundGradientStop: string;
  foreground: string;
  foregroundMuted: string;
  foregroundSubtle: string;
  accent: string;
  accentHover: string;
  accentMuted: string;
  accentContrast: string;
  border: string;
  borderStrong: string;
  success: string;
  successMuted: string;
  warning: string;
  warningMuted: string;
  danger: string;
  dangerMuted: string;
  focusRing: string;
  muted: string;
  ok: string;
  /** Placeholder degli input. Scuro: bianco. Chiaro: grigio scuro, leggibile sul fondo chiaro. */
  inputPlaceholder: string;
};

export const darkColors: AppColors = {
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
  accentContrast: palette.ivory100,
  border: palette.pitch600,
  borderStrong: palette.pitch500,
  success: palette.success500,
  successMuted: palette.success400,
  warning: palette.warning500,
  warningMuted: palette.warning400,
  danger: palette.danger500,
  dangerMuted: palette.danger400,
  focusRing: palette.focusRing,
  muted: palette.slate300,
  ok: palette.success500,
  inputPlaceholder: "#ffffff",
};

export const lightColors: AppColors = {
  background: palette.ivory50,
  backgroundSubtle: palette.ivory100,
  backgroundElevated: "#ffffff",
  backgroundGradientStop: palette.ivory200,
  foreground: palette.pitch900,
  foregroundMuted: palette.pitch500,
  foregroundSubtle: palette.slate500,
  accent: palette.electric500,
  accentHover: palette.electric600,
  accentMuted: palette.electric300,
  accentContrast: palette.ivory50,
  border: "#d9d3c7",
  borderStrong: "#b7b0a2",
  success: palette.success600,
  successMuted: palette.success500,
  warning: palette.warning600,
  warningMuted: palette.warning500,
  danger: palette.danger600,
  dangerMuted: palette.danger500,
  focusRing: palette.electric600,
  muted: palette.pitch500,
  ok: palette.success600,
  inputPlaceholder: palette.pitch500,
};

export function resolveColorScheme(
  preference: ThemePreference,
  systemScheme: string | null | undefined,
): ResolvedColorScheme {
  if (preference === "light" || preference === "dark") {
    return preference;
  }
  return systemScheme === "light" ? "light" : "dark";
}
