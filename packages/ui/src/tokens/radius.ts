/** Border radius tokens (px). */

export const radius = {
  none: 0,
  sm: 4,
  md: 12,
  lg: 16,
  xl: 24,
  pill: 9999,
} as const;

export type RadiusToken = keyof typeof radius;
