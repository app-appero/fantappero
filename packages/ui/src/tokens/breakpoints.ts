/** Responsive breakpoints (px) — mobile-first. */

export const breakpoints = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
} as const;

export type BreakpointToken = keyof typeof breakpoints;

/** Media query helpers for programmatic use (e.g. React Native Web). */
export const breakpointUp = (token: BreakpointToken): string =>
  `(min-width: ${breakpoints[token]}px)`;

export const breakpointDown = (token: BreakpointToken): string =>
  `(max-width: ${breakpoints[token] - 0.02}px)`;
