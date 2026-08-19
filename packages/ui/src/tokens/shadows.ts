/** Elevation shadows — dark UI tuned. */

export const shadows = {
  none: "none",
  sm: "0 1px 2px rgba(0, 0, 0, 0.35)",
  md: "0 4px 12px rgba(0, 0, 0, 0.4)",
  lg: "0 12px 32px rgba(0, 0, 0, 0.45)",
  focus: "0 0 0 3px rgba(143, 176, 247, 0.45)",
} as const;

export type ShadowToken = keyof typeof shadows;
