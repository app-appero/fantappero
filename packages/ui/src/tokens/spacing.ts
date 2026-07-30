/** Spacing scale (px) — 4px base grid. */

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 40,
  "2xl": 56,
  "3xl": 72,
} as const;

export type SpacingToken = keyof typeof spacing;

/** Layout density presets for fantasy sport interfaces. */
export const density = {
  /** Tables, mercato, rose — più righe visibili. */
  compact: {
    gap: spacing.sm,
    padding: spacing.sm,
    rowHeight: 36,
  },
  /** Default app e pannello admin. */
  comfortable: {
    gap: spacing.md,
    padding: spacing.md,
    rowHeight: 44,
  },
  /** Landing, onboarding, stati vuoto/errore. */
  spacious: {
    gap: spacing.lg,
    padding: spacing.xl,
    rowHeight: 52,
  },
} as const;

export type DensityToken = keyof typeof density;
