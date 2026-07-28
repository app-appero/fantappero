/** Shared design tokens (scaffold — no product UI yet). */

export const colors = {
  background: "#0f1419",
  foreground: "#f4f1ea",
  accent: "#2f6fed",
  muted: "#8b93a7",
  ok: "#2f9e44",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 40,
} as const;

export const typography = {
  fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
  fontSize: {
    sm: 14,
    md: 16,
    lg: 24,
    xl: 40,
  },
} as const;

export type ColorToken = keyof typeof colors;
